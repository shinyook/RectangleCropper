import unittest
import warnings

import numpy as np
from PIL import Image

from rectanglecropper.crop import ImageThresholdUtil, RectangleImageCrop


from crop_support import CropFixture


class CropTests(CropFixture, unittest.TestCase):
    def test_threshold_returns_intensity_not_index(self):
        result = ImageThresholdUtil.get_threshold_pixels(
            10, 10, np.full((10, 10), 255), 1, 10)
        self.assertEqual(result.tolist(), [255])

    def test_solid_image_with_default_candidates(self):
        cropper = self.open_array(np.full((20, 30), 255))
        cropper.crop()
        self.assertEqual(cropper.get_crop_points(), [])

    def test_black_background_is_not_empty_threshold(self):
        cropper = self.open_array(self.rectangle(background=0))
        self.assertEqual(self.crop(cropper), [(3, 4, 12, 10)])
        self.assertEqual(cropper.get_threshold_pixels().tolist(), [0])

    def test_multiple_background_values(self):
        array = self.rectangle()
        array[:, 15:] = 200
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper, candidate_threshold_group=2),
                         [(3, 4, 12, 10)])
        self.assertEqual(set(cropper.get_threshold_pixels()), {200, 255})

    def test_no_background_has_explicit_error(self):
        cropper = self.open_array(np.arange(100).reshape(10, 10))
        with self.assertRaisesRegex(RuntimeError, 'No threshold pixels'):
            self.crop(cropper)
        self.assertEqual(cropper.get_crop_points(), [])

    def test_bounds_include_all_component_extents(self):
        # Scan starts at the lower-left tip, not the top-left of the bounds.
        array = np.full((20, 30), 255)
        array[10, 2:13] = 100
        array[2:11, 12] = 100
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper), [(2, 2, 13, 11)])

    def test_minimum_dimensions_are_inclusive_and_not_swapped(self):
        cropper = self.open_array(self.rectangle())
        self.assertEqual(self.crop(cropper, min_crop_width=9, min_crop_height=6),
                         [(3, 4, 12, 10)])
        self.assertEqual(self.crop(cropper, min_crop_width=10, min_crop_height=6), [])
        self.assertEqual(self.crop(cropper, min_crop_width=9, min_crop_height=7), [])

    def test_instances_do_not_share_results(self):
        first = self.open_array(self.rectangle())
        self.crop(first)
        second = RectangleImageCrop()
        self.assertEqual(second.get_crop_points(), [])
        second = self.open_array(np.full((20, 30), 255), second)
        self.crop(second)
        self.assertEqual(first.get_crop_points(), [(3, 4, 12, 10)])

    def test_repeated_crop_recomputes_without_duplicates(self):
        cropper = self.open_array(self.rectangle())
        expected = [(3, 4, 12, 10)]
        self.assertEqual(self.crop(cropper), expected)
        self.assertEqual(self.crop(cropper), expected)
        self.assertEqual(self.crop(cropper, min_crop_width=20), [])
        self.assertEqual(self.crop(cropper), expected)

    def test_open_resets_results_and_thresholds(self):
        cropper = self.open_array(self.rectangle())
        self.crop(cropper)
        self.open_array(np.full((20, 30), 255), cropper)
        self.assertEqual(cropper.get_crop_points(), [])
        with self.assertRaises(RuntimeError):
            cropper.get_threshold_pixels()
        self.assertEqual(self.crop(cropper), [])

    def test_saved_image_keeps_last_row_and_column(self):
        array = self.rectangle()
        array[9, 3:12] = 110
        array[4:10, 11] = 120
        cropper = self.open_array(array)
        self.crop(cropper)
        cropper.save(str(self.root), 'result', 'PNG')
        with Image.open(self.root / 'result_1.png') as result:
            self.assertEqual(result.size, (9, 6))
            np.testing.assert_array_equal(np.array(result)[:, :, 0], array[4:10, 3:12])

    def test_single_pixel_and_image_edges(self):
        array = np.full((20, 30), 255)
        array[0, 0] = 100
        array[19, 29] = 100
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper), [(0, 0, 1, 1), (29, 19, 30, 20)])

    def test_warning_uses_current_options(self):
        cropper = self.open_array(self.rectangle())
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.crop(cropper, occupancy_rate=6, pixel_sensitivity=11,
                      candidate_threshold_group=6)
        messages = [str(item.message) for item in caught]
        self.assertTrue(any('occupancy_rate' in message for message in messages))
        self.assertTrue(any('candidate_threshold_group' in message for message in messages))
        self.assertTrue(any('pixel_sensitivity' in message for message in messages))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.crop(cropper)
        self.assertEqual(caught, [])

    def test_crop_before_open_has_explicit_error(self):
        with self.assertRaisesRegex(RuntimeError, 'open method'):
            self.crop(RectangleImageCrop())


if __name__ == '__main__':
    unittest.main()
