import unittest

import numpy as np

from rectcropper._core import _rgb_foreground, _rounded_intensity


class MaskOptimizationTests(unittest.TestCase):
    def test_integer_mean_matches_all_possible_channel_sums(self):
        sums = np.arange(766, dtype=np.uint16)
        red = np.minimum(sums, 255)
        green = np.minimum(sums-red, 255)
        blue = sums-red-green
        rgb = np.stack((red, green, blue), axis=-1).astype(np.uint8).reshape(766, 1, 3)
        expected = np.rint(rgb.mean(axis=2)).astype(np.uint8)
        np.testing.assert_array_equal(_rounded_intensity(rgb), expected)

    def test_rgb_mask_matches_signed_reference_at_boundaries(self):
        random = np.random.default_rng(215)
        rgb = random.integers(0, 256, (37, 49, 3), dtype=np.uint8)
        colors = np.array([[0, 0, 0], [255, 255, 255], [0, 255, 128], [30, 90, 150]], dtype=np.int16)
        rgb[0, :4] = colors
        original = rgb.copy()
        for sensitivity in (0, 1, 5, 10, 127, 254, 255):
            for candidates in (colors[:1], colors[1:2], colors[2:], colors):
                expected = np.ones(rgb.shape[:2], dtype=bool)
                for color in candidates:
                    expected &= np.any(np.abs(rgb.astype(np.int16)-color) > sensitivity, axis=2)
                actual = _rgb_foreground(rgb, candidates, sensitivity)
                np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(rgb, original)
