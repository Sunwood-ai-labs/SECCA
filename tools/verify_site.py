"""Check built documentation resources and internal links without a browser."""

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.ids = set()
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if values.get('id'):
            self.ids.add(values['id'])
        for name in ('href', 'src'):
            if values.get(name):
                self.links.append(values[name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('docs/.vitepress/dist'))
    parser.add_argument('--base', default='/SECCA/')
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    pages = {path: Page(path.read_text(encoding='utf-8')) for path in root.rglob('*.html')}
    failures = []
    checked = 0
    for source, page in pages.items():
        for link in page.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            value = unquote(parsed.path)
            if value.startswith('/'):
                if not value.startswith(args.base):
                    failures.append(f'Link misses site base: {source.relative_to(root)} -> {value}')
                    continue
                target = root / value[len(args.base):]
            elif value:
                target = source.parent / value
            else:
                target = source
            target = target.resolve()
            if not target.is_relative_to(root):
                failures.append('Link escapes documentation output')
                continue
            candidates = [target]
            if target.suffix == '':
                candidates += [target.with_suffix('.html'), target / 'index.html']
            target = next((item for item in candidates if item.is_file()), None)
            checked += 1
            if target is None:
                failures.append(f'Missing resource: {source.relative_to(root)} -> {value}')
            elif parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target].ids:
                failures.append(f'Missing fragment: {source.relative_to(root)} -> {link}')
    print(json.dumps({'status': 'passed' if not failures else 'failed', 'pages': len(pages),
                      'internal_links_checked': checked, 'failures': failures}, ensure_ascii=False))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
