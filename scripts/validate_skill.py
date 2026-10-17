"""Validate the portable SECCA skill entrypoint and invocation metadata."""

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent


def validate(root):
    root = Path(root).resolve(strict=True)
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if match is None:
        raise ValueError("SKILL.md requires YAML frontmatter")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict) or metadata.get("name") != "secca":
        raise ValueError("Skill name must be secca")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Skill description must be a nonempty string")
    config = yaml.safe_load((root / "agents/openai.yaml").read_text(encoding="utf-8"))
    interface = config.get("interface") if isinstance(config, dict) else None
    if not isinstance(interface, dict) or interface.get("display_name") != "SECCA":
        raise ValueError("Skill display name must be SECCA")
    prompt = interface.get("default_prompt")
    if not isinstance(prompt, str) or not re.search(r"\$secca(?![A-Za-z0-9_-])", prompt):
        raise ValueError("Skill default prompt must invoke $secca")
    links = []
    for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", text[match.end():]):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = (root / unquote(parsed.path)).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Skill local link is missing or outside the repository: " + target)
        links.append(parsed.path)
    return {"success": True, "name": "secca", "display_name": "SECCA", "local_links_checked": sorted(set(links))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="SECCA skill root; defaults to this checkout")
    args = parser.parse_args()
    try:
        result = validate(args.root)
    except (OSError, ValueError, yaml.YAMLError) as error:
        print("validate_skill: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
