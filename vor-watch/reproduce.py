"""Rebuild three published PDF change notices from six checksum-pinned public PDFs."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from vorwatch import compare


BASE = Path(__file__).resolve().parent


def disk_hash(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def valid(path, source):
    return path.is_file() and path.stat().st_size == source['bytes'] and disk_hash(path) == source['sha256']


def get_source(path, source, offline):
    if valid(path, source):
        return
    if path.exists():
        raise ValueError(f'{path}: stored source differs from the published checksum; preserve it separately before retrying')
    if offline:
        raise FileNotFoundError(f'{path}: missing; re-run without --offline to download the six sources')
    path.parent.mkdir(exist_ok=True, parents=True)
    request = Request(source['download'], headers={'User-Agent': 'VoRWatch/1.0 (academic PDF reproducibility check)'})
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        with urlopen(request, timeout=60) as resp, temp_path.open('wb') as out:
            size = 0
            while chunk := resp.read(65536):
                size += len(chunk)
                if size > source['bytes']:
                    raise ValueError(f'{source["download"]}: source now larger than expected')
                out.write(chunk)
        if not valid(temp_path, source):
            raise ValueError(f'{source["download"]}: source bytes differ; the archived edition could have changed')
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--cache', type=Path, default=Path('cache'))
    cli.add_argument('--offline', action='store_true')
    opts = cli.parse_args()
    cases = json.loads((BASE/'cases.json').read_text(encoding='utf-8'))
    for case in cases:
        folder = opts.cache / case['id']
        before, after = folder/'before.pdf', folder/'after.pdf'
        for filename, side in [(before,'before'),(after,'after')]:
            get_source(filename, case[side], opts.offline)
        report = compare(before, after, case['article'], case['official_notice'])
        expected = json.loads((BASE/case['record']).read_text(encoding='utf-8'))
        if report != expected:
            raise ValueError(f'{case["id"]}: generated notice differs; compare PyMuPDF and MuPDF versions')
        print(f'{case["publisher"]}: verified {report["notice_id"]}')


if __name__ == '__main__':
    main()
