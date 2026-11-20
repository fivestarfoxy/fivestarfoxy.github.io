"""Compare two PDF editions and publish a portable change notice. No network access."""
import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

import pymupdf


DPI = 96
GRID = 8


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def snapshot(path):
    raw = Path(path).read_bytes()
    pages = []
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        if doc.needs_pass or not len(doc):
            raise ValueError('A readable, unencrypted PDF with at least one page is required.')
        for page in doc:
            text = page.get_text('text', sort=True)
            pixels = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csRGB, alpha=False, annots=True)
            samples = pixels.samples_mv
            # Cover the entire rendered page, including vector art and scanned page images.
            tiles = []
            for row in range(GRID):
                y0, y1 = row*pixels.height//GRID, (row+1)*pixels.height//GRID
                for col in range(GRID):
                    x0, x1 = col*pixels.width//GRID, (col+1)*pixels.width//GRID
                    digest = hashlib.sha256()
                    for y in range(y0, y1):
                        i = y * pixels.stride
                        digest.update(samples[i+3*x0:i+3*x1])
                    tiles.append(digest.hexdigest())
            pages.append({'size_px': [pixels.width, pixels.height], 'visual_sha256': sha(samples),
                          'text_sha256': sha(text.encode()), 'text': text, 'tiles': tiles})
    return sha(raw), pages


def first_edit(a, b):
    lines_a, lines_b = a.splitlines(), b.splitlines()
    for tag, i, j, k, end in difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False).get_opcodes():
        if tag != 'equal':
            return {'before_line': i+1, 'removed_lines': j-i, 'after_line': k+1, 'added_lines': end-k}
    return None


def compare(before, after, article, official_notice=None):
    h1, old = snapshot(before)
    h2, new = snapshot(after)
    changes = []
    for idx in range(max(len(old), len(new))):
        if idx >= len(old) or idx >= len(new):
            changes.append({'page': idx+1, 'status': 'added' if idx >= len(old) else 'removed'})
            continue
        a, b = old[idx], new[idx]
        different_text = a['text_sha256'] != b['text_sha256']
        different_geometry = a['size_px'] != b['size_px']
        different_picture = different_geometry or a['visual_sha256'] != b['visual_sha256']
        if not (different_text or different_picture):
            continue
        entry = {'page': idx+1, 'status': 'changed', 'text_changed': different_text,
                 'appearance_changed': different_picture, 'page_size_changed': different_geometry}
        if different_text:
            entry['first_text_difference'] = first_edit(a['text'], b['text'])
        if different_picture:
            entry['changed_tiles'] = [[i//GRID+1, i%GRID+1] for i in range(GRID*GRID)
                                      if different_geometry or a['tiles'][i] != b['tiles'][i]]
        changes.append(entry)

    def summary(digest, pages):
        return {'file_sha256': digest, 'pages': [{k: p[k] for k in ('size_px','text_sha256','visual_sha256')}
                                                for p in pages]}

    report = {'format': 'vorwatch/1', 'article': article, 'official_notice': official_notice,
              'renderer': {'library': 'PyMuPDF', 'version': pymupdf.VersionBind,
                           'mupdf': pymupdf.VersionFitz, 'dpi': DPI, 'rgb': True, 'tile_grid': [GRID, GRID]},
              'transition_id': 'sha256:' + sha(canonical([article, h1, h2])),
              'before': summary(h1,old), 'after': summary(h2,new),
              'file_changed': h1 != h2, 'changed_pages': changes}
    report['notice_id'] = 'sha256:' + sha(canonical(report))
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='command', required=True)
    record = commands.add_parser('compare', help='record changes and the optional official notice URL')
    check = commands.add_parser('verify', help='independently regenerate and verify a notice from the two PDFs')
    for cmd in (record, check):
        cmd.add_argument('before', type=Path)
        cmd.add_argument('after', type=Path)
    record.add_argument('--article', required=True, help='canonical article DOI URL')
    record.add_argument('--official-notice', help='publisher correction URL when one exists')
    record.add_argument('--out', required=True, type=Path)
    check.add_argument('notice', type=Path)
    args = cli.parse_args()
    if args.command == 'compare':
        report = compare(args.before, args.after, args.article, args.official_notice)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print(report['notice_id'])
        return 0
    expected = json.loads(args.notice.read_text(encoding='utf-8'))
    actual = compare(args.before, args.after, expected['article'], expected['official_notice'])
    if actual != expected:
        print('Verification failed: PDF bytes, rendering environment or report differ.', file=sys.stderr)
        return 1
    print('Verified', expected['notice_id'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
