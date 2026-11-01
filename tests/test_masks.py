from contextlib import redirect_stdout
from io import StringIO
import unittest

import numpy as np
from PIL import Image, ImageDraw

from crop_support import CropFixture
from rectcropper import RectangleCropper, crop_image
from rectcropper.__main__ import main


class MaskTests(CropFixture, unittest.TestCase):
    def irregular(self):
        image = np.full((20, 30), 255, dtype=np.uint8)
        image[2:12, 3:6] = 100
        image[9:12, 3:15] = 100
        return image

    def test_object_mask_matches_irregular_component(self):
        array = self.irregular()
        cropper = self.open_array(array)
        self.crop(cropper, output_shape='object')
        self.assertEqual(cropper.get_crop_points(), [(3, 2, 15, 12)])
        mask = next(cropper.iter_masks())
        result = next(cropper.iter_crops())
        expected = np.where(array[2:12, 3:15] == 100, 255, 0).astype(np.uint8)
        self.assertEqual(mask.mode, 'L')
        self.assertEqual(result.mode, 'RGBA')
        np.testing.assert_array_equal(np.array(mask), expected)
        np.testing.assert_array_equal(np.array(result.getchannel('A')), expected)

    def test_circle_object_and_hole(self):
        image = Image.new('RGB', (40, 40), 'white')
        draw = ImageDraw.Draw(image)
        draw.ellipse((5, 5, 34, 34), fill=(100,)*3)
        draw.ellipse((13, 13, 26, 26), fill='white')
        cropper = self.open_array(np.array(image))
        self.crop(cropper, output_shape='object')
        result = next(cropper.iter_crops())
        expected = (np.array(image)[5:35, 5:35, 0] == 100).astype(np.uint8)*255
        np.testing.assert_array_equal(np.array(result.getchannel('A')), expected)
        self.assertEqual(result.getpixel((15, 15))[3], 0)

    def test_nested_component_is_not_included_in_other_mask(self):
        image = Image.new('RGB', (40, 40), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((4, 4, 35, 35), outline=(100,)*3, width=3)
        draw.rectangle((15, 15, 20, 20), fill=(100,)*3)
        cropper = self.open_array(np.array(image))
        self.crop(cropper, output_shape='object', padding=3)
        results = list(cropper.iter_crops())
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].getpixel((15, 15))[3], 0)
        self.assertEqual(results[1].getpixel((3, 3))[3], 255)
        self.assertEqual(results[1].getpixel((0, 0))[3], 0)

    def test_padding_transparent_and_clipped(self):
        array = self.rectangle()
        cropper = self.open_array(array)
        self.crop(cropper, output_shape='object', padding=5)
        self.assertEqual(cropper.get_crop_points(), [(0, 0, 17, 15)])
        result = next(cropper.iter_crops())
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((3, 4))[3], 255)
        self.assertEqual(np.count_nonzero(np.array(result.getchannel('A'))), 54)

    def test_original_alpha_is_preserved(self):
        image = np.full((20, 30, 4), 255, dtype=np.uint8)
        image[4:10, 3:12] = (100, 100, 100, 128)
        path = self.root / 'alpha.png'
        Image.fromarray(image).save(path)
        cropper = RectangleCropper()
        cropper.open(path)
        self.crop(cropper, output_shape='object', padding=1)
        result = next(cropper.iter_crops())
        self.assertEqual(result.getpixel((1, 1))[3], 128)
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        # Binary masks represent selection, independent of source opacity.
        self.assertEqual(next(cropper.iter_masks()).getpixel((1, 1)), 255)

    def test_geometric_shapes_are_centered_and_distinct(self):
        cropper = self.open_array(self.rectangle())
        self.crop(cropper, output_shape='circle')
        circle = np.array(next(cropper.iter_masks()))
        self.assertEqual(circle.shape, (6, 9))
        self.assertTrue(np.all(circle[:, 0] == 0))
        self.assertTrue(np.all(circle[:, 7:] == 0))
        self.assertEqual(circle[3, 3], 255)
        self.crop(cropper, output_shape='ellipse')
        ellipse = np.array(next(cropper.iter_masks()))
        self.assertEqual(ellipse[3, 0], 255)
        self.assertEqual(ellipse[0, 0], 0)
        self.assertGreater(np.count_nonzero(ellipse), np.count_nonzero(circle))

    def test_single_pixel_and_thin_geometry(self):
        for height, width in [(1, 1), (1, 6), (6, 1)]:
            array = np.full((20, 30), 255)
            array[2:2+height, 3:3+width] = 100
            cropper = self.open_array(array)
            for shape in ('rectangle', 'object', 'circle', 'ellipse'):
                with self.subTest(height=height, width=width, shape=shape):
                    self.crop(cropper, output_shape=shape)
                    mask = np.array(next(cropper.iter_masks()))
                    self.assertGreater(np.count_nonzero(mask), 0)

    def test_masks_are_independent_and_state_is_reset(self):
        cropper = self.open_array(self.irregular())
        self.crop(cropper, output_shape='object')
        mask = next(cropper.iter_masks())
        mask.paste(0, (0, 0, *mask.size))
        self.assertEqual(next(cropper.iter_masks()).getpixel((0, 0)), 255)
        self.crop(cropper)
        self.assertEqual(next(cropper.iter_crops()).mode, 'RGB')
        self.assertTrue(np.all(np.array(next(cropper.iter_masks())) == 255))
        self.open_array(self.rectangle(), cropper)
        self.assertEqual(list(cropper.iter_masks()), [])
        self.assertEqual(list(cropper.iter_crops()), [])

    def test_empty_result_and_failed_detection_clear_masks(self):
        cropper = self.open_array(self.irregular())
        self.crop(cropper, output_shape='object')
        self.crop(cropper, output_shape='object', min_area=1000)
        self.assertEqual(list(cropper.iter_masks()), [])
        with self.assertRaises(RuntimeError):
            self.crop(cropper, occupancy_rate=99, output_shape='object')
        self.assertEqual(list(cropper.iter_masks()), [])

    def test_default_rectangle_stays_unchanged(self):
        cropper = self.open_array(self.irregular())
        self.crop(cropper)
        result = next(cropper.iter_crops())
        self.assertEqual(result.mode, 'RGB')
        self.assertEqual(result.getpixel((10, 0)), (255, 255, 255))

    def test_one_call_and_png_jpeg_saving(self):
        self.open_array(self.irregular())
        images = crop_image(self.root/'source.png', output_shape='object',
                            output_dir=self.root/'out', min_crop_width=1, min_crop_height=1)
        self.assertEqual(images[0].getpixel((10, 0))[3], 0)
        with Image.open(self.root/'out'/'source_1.png') as saved:
            np.testing.assert_array_equal(np.array(saved), np.array(images[0]))
        crop_image(self.root/'source.png', output_shape='object', output_format='jpeg',
                   output_dir=self.root/'out', min_crop_width=1, min_crop_height=1)
        with Image.open(self.root/'out'/'source_1.jpeg') as saved:
            self.assertEqual(saved.mode, 'RGB')
            self.assertGreater(min(saved.getpixel((10, 0))), 240)

    def test_cli_shape(self):
        self.open_array(self.irregular())
        with redirect_stdout(StringIO()):
            main([str(self.root/'source.png'), '-o', str(self.root/'out'),
                  '--shape', 'object', '--min-width', '1', '--min-height', '1'])
        with Image.open(self.root/'out'/'source_1.png') as image:
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.getpixel((10, 0))[3], 0)

    def test_invalid_shape_and_masks_before_open(self):
        cropper = self.open_array(self.rectangle())
        with self.assertRaisesRegex(ValueError, 'output_shape'):
            self.crop(cropper, output_shape='triangle')
        with self.assertRaisesRegex(RuntimeError, 'open method'):
            next(RectangleCropper().iter_masks())
