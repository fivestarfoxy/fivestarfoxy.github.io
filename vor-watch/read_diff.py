"""Print the line diff for a selected page of two local PDFs."""
import argparse
import difflib
from pathlib import Path
import pymupdf


def lines(path, page):
    with pymupdf.open(path) as doc:
        if not 1 <= page <= len(doc):
            raise ValueError(f'{path.name} has {len(doc)} pages; requested {page}')
        return doc[page-1].get_text('text', sort=True).splitlines()


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('before', type=Path)
    cli.add_argument('after', type=Path)
    cli.add_argument('page', type=int)
    args = cli.parse_args()
    for line in difflib.unified_diff(lines(args.before,args.page),lines(args.after,args.page),
                                     fromfile='before',tofile='after',lineterm=''):
        print(line)
