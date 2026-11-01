import unittest
from collections import deque

import numpy as np
from PIL import Image

from crop_support import CropFixture


class FeatureTests(CropFixture, unittest.TestCase):
    def test_histogram_matches_unique_value_reference(self):
        from rectanglecropper.crop import ImageThresholdUtil
        random = np.random.default_rng(7)
        for _ in range(30):
            image = random.integers(0, 8, size=(20, 30), dtype=np.uint8) * 30
            values, counts = np.unique(image, return_counts=True)
            for candidates in (1, 3, 20):
                selected = np.argsort(counts, kind='stable')[-min(candidates, len(values)):]
                expected = values[selected[counts[selected] / image.size * 100 > 10]]
                actual = ImageThresholdUtil.get_threshold_pixels(30, 20, image, candidates, 10)
                np.testing.assert_array_equal(actual, expected)

    def test_border_rgb_distinguishes_equal_mean_colors(self):
        array = np.full((20, 30, 3), (255, 0, 0), dtype=np.uint8)
        array[4:10, 3:12] = (0, 255, 0)
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper), [])
        self.assertEqual(self.crop(cropper, background_mode='border'), [(3, 4, 12, 10)])
        np.testing.assert_array_equal(cropper.get_threshold_pixels(), [[255, 0, 0]])

    def test_border_avoids_dominant_foreground_color(self):
        array = np.full((20, 30), 255)
        array[1:19, 1:29] = 100
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper, background_mode='border'), [(1, 1, 29, 19)])

    def test_border_groups_small_color_variations(self):
        array = np.full((20, 30, 3), 240, dtype=np.uint8)
        array[::2, :] = 244
        array[4:10, 3:12] = (0, 100, 200)
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper, background_mode='border'), [(3, 4, 12, 10)])

    def test_manual_background_and_disabled_auto_detection(self):
        cropper = self.open_array(self.rectangle())
        cropper.open(self.root / 'source.png', auto_threshold_detection=False)
        with self.assertRaisesRegex(ValueError, 'background_colors'):
            self.crop(cropper)
        self.assertEqual(self.crop(cropper, background_colors=[(255, 255, 255)]),
                         [(3, 4, 12, 10)])

    def test_multiple_manual_background_colors(self):
        array = self.rectangle()
        array[:, 15:] = 200
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper, background_colors=[(255,)*3, (200,)*3]),
                         [(3, 4, 12, 10)])

    def test_area_counts_pixels_instead_of_bounding_box(self):
        array = np.full((20, 30), 255)
        array[2, 2:12] = 100
        array[2:12, 2] = 100  # 19 pixels in a 100-pixel box
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper, min_area=19), [(2, 2, 12, 12)])
        self.assertEqual(self.crop(cropper, min_area=20), [])

    def test_padding_clips_and_filters_before_expansion(self):
        cropper = self.open_array(self.rectangle())
        self.assertEqual(self.crop(cropper, padding=5), [(0, 0, 17, 15)])
        self.assertEqual(self.crop(cropper, padding=5, min_crop_width=10), [])

    def test_diagonal_connectivity(self):
        array = np.full((20, 30), 255)
        array[2, 2] = array[3, 3] = 100
        cropper = self.open_array(array)
        self.assertEqual(self.crop(cropper), [(2, 2, 3, 3), (3, 3, 4, 4)])
        self.assertEqual(self.crop(cropper, connectivity=8), [(2, 2, 4, 4)])

    def test_iter_crops_are_independent(self):
        cropper = self.open_array(self.rectangle())
        self.crop(cropper)
        first = next(cropper.iter_crops())
        first.putpixel((0, 0), (0, 0, 0))
        self.assertEqual(next(cropper.iter_crops()).getpixel((0, 0)), (100, 100, 100))

    def test_rgba_png_and_jpeg_directory_creation(self):
        array = np.full((20, 30, 4), 255, dtype=np.uint8)
        array[4:10, 3:12] = (100, 100, 100, 128)
        path = self.root / 'rgba.png'
        Image.fromarray(array).save(path)
        from rectanglecropper.crop import RectangleImageCrop
        cropper = RectangleImageCrop()
        cropper.open(path)
        self.crop(cropper)
        output = self.root / 'nested' / 'crops'
        cropper.save(output, 'crop', 'PNG')
        cropper.save(output, 'crop', 'jpg')
        with Image.open(output / 'crop_1.png') as image:
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.getpixel((0, 0)), (100, 100, 100, 128))
        with Image.open(output / 'crop_1.jpg') as image:
            self.assertEqual(image.mode, 'RGB')
            self.assertEqual(image.size, (9, 6))

    def test_exif_orientation(self):
        array = self.rectangle()
        image = Image.fromarray(array)
        exif = image.getexif()
        exif[274] = 6
        path = self.root / 'oriented.png'
        image.save(path, exif=exif)
        from rectanglecropper.crop import RectangleImageCrop
        cropper = RectangleImageCrop()
        cropper.open(path)
        self.assertEqual(self.crop(cropper), [(10, 3, 16, 12)])

    def test_invalid_options(self):
        cropper = self.open_array(self.rectangle())
        cases = [dict(connectivity=5), dict(padding=-1), dict(min_area=0),
                 dict(occupancy_rate=100), dict(pixel_sensitivity=256),
                 dict(background_mode='unknown'), dict(background_colors=[]),
                 dict(background_colors=[(255, 0)]), dict(background_colors=[(-1, 0, 0)]),
                 dict(background_colors=[(np.nan, 0, 0)]), dict(background_colors=[(0.5, 0, 0)])]
        for options in cases:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.crop(cropper, **options)
        with self.assertRaises(TypeError):
            self.crop(cropper, padding=True)

    def test_thresholds_are_defensive_copy(self):
        cropper = self.open_array(self.rectangle())
        self.crop(cropper)
        values = cropper.get_threshold_pixels()
        values[:] = 0
        self.assertEqual(cropper.get_threshold_pixels().tolist(), [255])

    def test_one_pixel_dimensions_in_border_mode(self):
        for shape in [(1, 20), (20, 1), (1, 1)]:
            cropper = self.open_array(np.full(shape, 255))
            self.assertEqual(self.crop(cropper, background_mode='border'), [])

    def test_random_masks_match_independent_flood_fill(self):
        random = np.random.default_rng(42)
        for connectivity in (4, 8):
            for _ in range(20):
                mask = random.random((15, 23)) < 0.35
                expected = []
                visited = set()
                for x in range(mask.shape[1]):
                    for y in range(mask.shape[0]):
                        if not mask[y, x] or (y, x) in visited:
                            continue
                        queue = deque([(y, x)])
                        visited.add((y, x))
                        points = []
                        while queue:
                            row, col = queue.popleft()
                            points.append((row, col))
                            for dy in (-1, 0, 1):
                                for dx in (-1, 0, 1):
                                    if not (dy or dx) or (connectivity == 4 and abs(dy)+abs(dx) != 1):
                                        continue
                                    ny, nx = row+dy, col+dx
                                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and (ny, nx) not in visited:
                                        visited.add((ny, nx))
                                        queue.append((ny, nx))
                        ys, xs = zip(*points)
                        expected.append((min(xs), min(ys), max(xs)+1, max(ys)+1))
                cropper = self.open_array(np.where(mask, 100, 255))
                actual = self.crop(cropper, connectivity=connectivity,
                                   background_colors=[(255, 255, 255)])
                self.assertEqual(actual, expected)
