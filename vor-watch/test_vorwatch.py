import tempfile
import unittest
from pathlib import Path

import pymupdf

from vorwatch import compare


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.first = self.root / 'first.pdf'
        self.other = self.root / 'other.pdf'

    def pdf(self, path, text='a', color=None, subject='baseline', pages=1):
        with pymupdf.open() as doc:
            for _ in range(pages):
                p = doc.new_page(width=120, height=120)
                p.insert_text((12, 24), text)
                if color:
                    p.draw_rect((20, 60, 60, 85), fill=color, color=color)
            doc.set_metadata({'subject': subject})
            doc.save(path)

    def report(self):
        return compare(self.first, self.other, 'https://doi.org/fixture', None)

    def test_identical(self):
        self.pdf(self.first)
        self.other.write_bytes(self.first.read_bytes())
        r = self.report()
        self.assertFalse(r['file_changed'])
        self.assertEqual(r['changed_pages'], [])
        self.assertEqual(r, self.report())

    def test_metadata_only(self):
        self.pdf(self.first)
        self.pdf(self.other, subject='updated subject')
        r = self.report()
        self.assertTrue(r['file_changed'])
        self.assertEqual(r['changed_pages'], [])

    def test_figure_only(self):
        self.pdf(self.first, color=(1, 0, 0))
        self.pdf(self.other, color=(0, 1, 0))
        change, = self.report()['changed_pages']
        self.assertFalse(change['text_changed'])
        self.assertTrue(change['appearance_changed'])
        self.assertTrue(0 < len(change['changed_tiles']) < 64)

    def test_text_and_page_count(self):
        self.pdf(self.first)
        self.pdf(self.other, text='corrected', pages=2)
        a, b = self.report()['changed_pages']
        self.assertEqual(a['first_text_difference'], {'before_line': 1, 'after_line': 1, 'removed_lines': 1, 'added_lines': 1})
        self.assertEqual(b, {'page': 2, 'status': 'added'})
        deleted = compare(self.other,self.first,'https://doi.org/fixture',None)['changed_pages'][1]
        self.assertEqual(deleted['status'], 'removed')

    def test_notice_link_is_bound_to_file_pair(self):
        self.pdf(self.first)
        self.pdf(self.other, text='corrected')
        a = self.report()
        b = compare(self.first,self.other,a['article'],'https://example.org/correction')
        self.assertNotEqual(a['notice_id'], b['notice_id'])
        self.assertEqual(a['before'], b['before'])
        self.assertEqual(a['transition_id'], b['transition_id'])

    def test_invalid_input(self):
        self.pdf(self.first)
        self.other.write_bytes(b'not a PDF')
        with self.assertRaises(pymupdf.FileDataError):
            self.report()


if __name__ == '__main__':
    unittest.main()
