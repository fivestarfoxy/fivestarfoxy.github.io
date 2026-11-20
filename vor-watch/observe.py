"""Archive a local published PDF and issue a notice when its bytes change (Linux/macOS)."""
import argparse
import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from vorwatch import compare, sha


def save(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        name = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            name.unlink(missing_ok=True)
            raise
    try:
        name.replace(path)
    finally:
        name.unlink(missing_ok=True)


def observe(archive, article, pdf, official_notice=None):
    raw = pdf.read_bytes()
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        if not len(doc) or doc.needs_pass:
            raise ValueError('Expected a readable published PDF.')
    digest = sha(raw)
    folder = archive / sha(article.encode())
    folder.mkdir(exist_ok=True, parents=True)
    index = folder/'records.json'
    with (folder/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = json.loads(index.read_text()) if index.exists() else []
        last = records[-1]['pdf_sha256'] if records else None
        if digest == last:
            return 'unchanged', index
        current = folder/(digest+'.pdf')
        if current.exists() and sha(current.read_bytes()) != digest:
            raise ValueError('Prior archive copy failed verification')
        if not current.exists():
            save(current, raw)
        event = {'article':article, 'observed_utc':datetime.now(timezone.utc).isoformat(), 'pdf_sha256':digest,
                 'previous_pdf_sha256':last, 'notice':None}
        if last:
            previous = folder/(last+'.pdf')
            if sha(previous.read_bytes()) != last:
                raise ValueError('Previous baseline failed verification')
            report = compare(previous, current, article, official_notice)
            name = report['notice_id'].split(':',1)[1]+'.json'
            save(folder/name, (json.dumps(report,indent=2,ensure_ascii=False)+'\n').encode())
            event['notice'] = name
        records.append(event)
        save(index, (json.dumps(records,indent=2,ensure_ascii=False)+'\n').encode())
        return ('change' if last else 'baseline'), index


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('article',help='canonical article DOI URL, used consistently for every observation')
    p.add_argument('pdf',type=Path)
    p.add_argument('--official-notice')
    args = p.parse_args()
    print(*observe(args.archive,args.article,args.pdf,args.official_notice))
