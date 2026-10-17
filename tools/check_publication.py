"""Check public files, pinned workflows, local Markdown links and experiment exports."""

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import zipfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.git', '.venv', '__pycache__', 'node_modules', '.audit', '.yomiyasu', '.pytest_cache', '.ruff_cache'}
REQUIRED = ['README.md', 'README.ja.md', 'SKILL.md', 'LICENSE', 'NOTICE.md', 'THIRD_PARTY_NOTICES.md',
            'CONTRIBUTING.md', 'SECURITY.md', 'CITATION.cff', 'CHANGELOG.md', 'pyproject.toml', 'uv.lock',
            'package.json', 'package-lock.json', '.github/workflows/ci.yml', '.github/workflows/pages.yml',
            'docs/index.md', 'docs/ja/index.md', 'experiments/beam-free-20261017/RESULT.json',
            'references/public-export-manifest.json']
SECRET_RULES = {
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b',
    'provider_token': rb'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|hf_[A-Za-z0-9]{24,})\b',
    'aws_access_key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'credential_url': rb'https?://[^\s/:@]{2,}:[^\s/@]{3,}@',
}


def public_files():
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True)
    if result.stdout:
        return [ROOT / name for name in result.stdout.decode().split('\0') if name]
    return [path for path in ROOT.rglob('*') if path.is_file()
            and not IGNORED.intersection(path.relative_to(ROOT).parts)
            and path.relative_to(ROOT).parts[0] not in {'dist', 'runs', 'runtime-proof'}
            and not path.relative_to(ROOT).as_posix().startswith('docs/.vitepress/dist/')
            and not path.relative_to(ROOT).as_posix().startswith('docs/.vitepress/cache/')]


def scan_payload(relative, payload):
    failures = []
    for name, pattern in SECRET_RULES.items():
        for match in re.finditer(pattern, payload):
            if (relative == 'scripts/test_gateway.py' and name == 'credential_url'
                    and match.group() == b'https' + b'://user' + b':pass@'):
                continue
            failures.append(f'Credential candidate: {relative} ({name}); matched value suppressed')
    if not relative.startswith('assets/'):
        homes = rb'(?i)[a-z]:[\\/]+Users[\\/]+[^\\/\s"\x27]+'
        host_home = rb'/home/(?!(?:candidate|opencode)(?:/|["\x27\s]))[A-Za-z0-9_.-]+/'
        label = b'embedding' + b'gemma2-lab'
        if re.search(homes, payload) or re.search(host_home, payload) or label in payload:
            failures.append(f'Unportable host metadata: {relative}; matched value suppressed')
    return failures


def markdown_links(path):
    relative = path.relative_to(ROOT).as_posix()
    if relative.startswith(('container/vendor/', 'assets/', 'references/verification/')):
        return []
    content = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8-sig'), flags=re.S)
    failures = []
    for link in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', content):
        parsed = urlsplit(link.strip('<>'))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        part = unquote(parsed.path)
        if '<' in part or '{' in part:
            continue
        if part.startswith('/'):
            if not relative.startswith('docs/'):
                failures.append(f'Nonportable absolute Markdown link: {relative}')
                continue
            part = part.removeprefix('/SECCA/') if part.startswith('/SECCA/') else part.lstrip('/')
            target = ROOT / 'docs' / part
            candidates = [target, target.with_suffix('.md'), target / 'index.md', ROOT / 'docs/public' / part]
        else:
            target = path.parent / part
            candidates = [target, target.with_suffix('.md'), target / 'index.md']
        if not any(candidate.exists() for candidate in candidates):
            failures.append(f'Broken Markdown link: {relative} -> {part}')
    return failures


def check_workflows():
    failures = []
    workflows = list((ROOT / '.github/workflows').glob('*.yml'))
    for path in workflows:
        document = yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
        if not isinstance(document.get('jobs'), dict) or 'on' not in document:
            failures.append(f'Invalid workflow structure: {path.name}')
        for job in document.get('jobs', {}).values():
            for step in job.get('steps', []):
                action = step.get('uses', '')
                if action and not action.startswith('./') and not re.fullmatch(r'[^@]+@[0-9a-f]{40}', action):
                    failures.append(f'Action is not commit-pinned: {path.name}')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    failures = [f'Missing public file: {name}' for name in REQUIRED if not (ROOT / name).is_file()]
    files = public_files()
    total = 0
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            failures.append(f'Unexpected published symlink: {relative}')
            continue
        size = path.stat().st_size
        total += size
        if size > 10 * 1024 * 1024:
            failures.append(f'Unexpected file above 10 MiB: {relative}')
        if path.name in {'.env', 'auth.json'} or path.suffix in {'.pem', '.key', '.oci'}:
            failures.append(f'Private runtime file selected for publication: {relative}')
        data = path.read_bytes()
        failures.extend(scan_payload(relative, data))
        if path.suffix.lower() == '.fcstd':
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith(('.xml', '.json', '.txt')):
                        failures.extend(scan_payload(relative + '!' + name, archive.read(name)))
        if path.suffix == '.md':
            failures.extend(markdown_links(path))
    failures.extend(check_workflows())
    for module_name in ('candidate', 'scores'):
        spec = importlib.util.spec_from_file_location(module_name, ROOT / 'scripts' / (module_name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        sys.path.insert(0, str(ROOT / 'scripts'))
        spec.loader.exec_module(module)
        if module_name == 'candidate':
            module.verify_assets()
        else:
            module.verify_baseline()
    spec = importlib.util.spec_from_file_location('build_context', ROOT / 'container/build_context.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    vendor_manifest = json.loads((ROOT / 'container/vendor/source-manifest.json').read_text(encoding='utf-8'))
    build.verified_vendor_files(ROOT / 'container/vendor/freecad-mcp', vendor_manifest)
    export = subprocess.run([sys.executable, str(ROOT / 'experiments/tools/verify_export.py')], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if export.returncode:
        failures.append('Published experiment verifier failed: ' + export.stderr.strip())
    historical = subprocess.run([sys.executable, str(ROOT / 'scripts/export_reference_records.py'),
                                 '--verify', '--output', str(ROOT)], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8')
    if historical.returncode:
        failures.append('Historical public export verifier failed: ' + historical.stderr.strip())
    result = {'status': 'passed' if not failures else 'failed', 'files_checked': len(files),
              'bytes_checked': total, 'failures': failures,
              'secret_scan_scope': 'Pattern checks including FCStd text members; absence of matches is not a guarantee.'}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
