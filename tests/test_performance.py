import unittest
from unittest.mock import patch

from crop_support import CropFixture
from scipy import ndimage
from PIL import Image
from rectcropper import RectangleCropper, crop_image

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


class ComponentOptimizationTests(CropFixture, unittest.TestCase):
    def scene(self):
        image = np.full((80, 110), 255, dtype=np.uint8)
        image[1:70:3, 1:70:3] = 100
        image[10:25, 80:100] = 100
        image[40:60, 80:100] = 100
        return image

    def test_remap_only_computes_retained_boxes_and_preserves_masks(self):
        cropper = self.open_array(self.scene())
        with patch('rectcropper._core.ndimage.find_objects', wraps=ndimage.find_objects) as boxes:
            actual = self.crop(cropper, min_area=10, output_shape='object')
        self.assertEqual(actual, [(80, 10, 100, 25), (80, 40, 100, 60)])
        self.assertEqual(boxes.call_args.kwargs['max_label'], 2)
        self.assertEqual([np.count_nonzero(np.array(mask)) for mask in cropper.iter_masks()], [300, 400])

    def test_all_rejected_skips_box_calculation(self):
        cropper = self.open_array(self.scene())
        with patch('rectcropper._core.ndimage.find_objects') as boxes:
            self.assertEqual(self.crop(cropper, min_area=1000, output_shape='object'), [])
        boxes.assert_not_called()
        self.assertEqual(list(cropper.iter_masks()), [])
        self.assertEqual(self.crop(cropper, min_area=10), [(80, 10, 100, 25), (80, 40, 100, 60)])


class CropRenderingTests(CropFixture, unittest.TestCase):
    def test_saving_and_returning_renders_each_mask_once(self):
        self.open_array(self.rectangle())
        original = RectangleCropper.iter_masks
        with patch.object(RectangleCropper, 'iter_masks', autospec=True, side_effect=original) as masks:
            images = crop_image(self.root/'source.png', output_dir=self.root/'out',
                                min_crop_width=1, min_crop_height=1, output_shape='object')
        self.assertEqual(masks.call_count, 1)
        with Image.open(self.root/'out'/'source_1.png') as saved:
            np.testing.assert_array_equal(np.array(saved), np.array(images[0]))

    def test_jpeg_save_does_not_change_returned_alpha(self):
        source = np.full((20, 30, 4), 255, dtype=np.uint8)
        source[4:10, 3:12] = (100, 100, 100, 128)
        path = self.root/'alpha.png'
        Image.fromarray(source).save(path)
        images = crop_image(path, output_dir=self.root/'out', output_format='jpeg',
                            min_crop_width=1, min_crop_height=1, output_shape='object', padding=1)
        self.assertEqual(images[0].mode, 'RGBA')
        self.assertEqual(images[0].getpixel((1, 1)), (100, 100, 100, 128))
        self.assertEqual(images[0].getpixel((0, 0))[3], 0)
        with Image.open(self.root/'out'/'alpha_1.jpeg') as saved:
            self.assertEqual(saved.mode, 'RGB')
            self.assertEqual(saved.size, images[0].size)
