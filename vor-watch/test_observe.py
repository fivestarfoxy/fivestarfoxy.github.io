import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from observe import observe
from vorwatch import compare


class CaptureTests(unittest.TestCase):
    def test_publish_with_missing_official_metadata_and_later_match(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder)
            files = []
            for i in range(2):
                file = d/f'{i}.pdf'
                with pymupdf.open() as doc:
                    doc.new_page().insert_text((30,90), str(i))
                    doc.save(file)
                files.append(file)
            article = 'https://doi.org/fixture'
            vault = d/'archive'
            self.assertEqual(observe(vault, article, files[0])[0], 'baseline')
            self.assertEqual(observe(vault, article, files[0])[0], 'unchanged')
            status, index = observe(vault, article, files[1])
            self.assertEqual(status, 'change')
            records = json.loads(index.read_text())
            self.assertEqual(len(records), 2)
            notice = json.loads((index.parent/records[1]['notice']).read_text())
            self.assertIsNone(notice['official_notice'])
            self.assertTrue(notice['changed_pages'][0]['text_changed'])
            linked = compare(*files, article, 'https://example.org/later-notice')
            self.assertEqual(linked['transition_id'], notice['transition_id'])
            self.assertNotEqual(linked['notice_id'], notice['notice_id'])
            self.assertEqual(observe(vault, article, files[1])[0], 'unchanged')


if __name__ == '__main__':
    unittest.main()
