"""Fetch selected paired CT and label TIFFs into images/ and labels/.

Data and terms: https://scrollprize.org/data_datasets (surface-labels)
Source dataset attribution: EduceLab-Scrolls / Vesuvius Challenge.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

BASE_URL="https://huggingface.co/buckets/scrollprize/datasets/resolve/surfaces/kaggle"


def fetch(kind, number, target_root, expected_hashes):
    name = f"sample_{number:05}.tif"
    target = target_root / kind / name
    key = f'{kind}/{name}'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        with target.open('rb') as src:
            digest = hashlib.file_digest(src,'sha256').hexdigest()
        if key in expected_hashes and digest != expected_hashes[key]:
            raise ValueError(f'Existing {key} failed the source checksum')
        return key,digest
    temporary = None
    try:
        with NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
            temporary = Path(tmp.name)
            with urlopen(f'{BASE_URL}/{key}', timeout=120) as resp:
                shutil.copyfileobj(resp,tmp)
        with temporary.open('rb') as src:
            if src.read(2) not in (b'II',b'MM'):
                raise ValueError(f'{key} is not a TIFF')
            src.seek(0)
            digest=hashlib.file_digest(src,'sha256').hexdigest()
        if key in expected_hashes and digest != expected_hashes[key]:
            raise ValueError(f'Downloaded {key} failed the published checksum')
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return key,digest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('samples',type=int,nargs='+')
    parser.add_argument('--data',type=Path,default=Path('.'))
    options=parser.parse_args()
    manifest=Path(__file__).with_name('SHA256SUMS')
    expected={}
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            digest,name=line.split(maxsplit=1)
            expected[name]=digest
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(fetch,kind,k,options.data,expected)
              for k in dict.fromkeys(options.samples) for kind in ('images','labels')]
        for job in jobs:
            file,digest=job.result();print(digest,file,flush=True)
