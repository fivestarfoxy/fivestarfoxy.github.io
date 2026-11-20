import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from anchor_trace import follow_trace
from trace_slice import load_slice


class TraceTests(unittest.TestCase):
    def test_constant_image_two_clicks_gives_chord(self):
        points = follow_trace(np.zeros((32, 36)), [(9, 5), (16, 20)])
        np.testing.assert_allclose(points[:, 0], 9 + 7 * (points[:, 1] - 5) / 15)

    def test_pins_each_click_and_reverses(self):
        rng = np.random.default_rng(4)
        image = rng.random((32, 40))
        anchors = np.array([[5, 9], [14, 10], [20, 19], [34, 14]])
        path = follow_trace(image, anchors)
        for anchor in anchors:
            self.assertTrue(np.any(np.all(path == anchor, axis=1)))
        np.testing.assert_allclose(path, follow_trace(image, anchors[::-1])[::-1], atol=1e-9)

    def test_rejects_outside_or_duplicate_anchors(self):
        for clicks in ([(-1, 3), (3, 3)], [(3, 3), (3, 3)]):
            with self.assertRaises(ValueError):
                follow_trace(np.zeros((20, 20)), clicks)

    def test_reads_specific_tiff_plane(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work) / 'stack.tif'
            frames = [Image.fromarray(np.full((8, 10), k, np.uint8)) for k in (2, 5, 9)]
            frames[0].save(p, save_all=True, append_images=frames[1:])
            np.testing.assert_array_equal(load_slice(p, 1, "0"), np.full((8, 10), 5))
            with self.assertRaises(ValueError):
                load_slice(p, 3, "0")

if __name__ == '__main__':
    unittest.main()
