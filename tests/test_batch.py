from concurrent.futures import Future
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from crop_support import CropFixture
from rectcropper import crop_image, crop_images


class BatchTests(CropFixture, unittest.TestCase):
    def paths(self, count=3):
        result = []
        for index in range(count):
            path = self.root / str(index) / 'same.png'
            path.parent.mkdir()
            Image.fromarray(self.rectangle()).save(path)
            result.append(path)
        return result

    def options(self):
        return dict(min_crop_width=1, min_crop_height=1, output_shape='object', padding=2)

    def test_serial_pixels_metadata_and_unique_names(self):
        paths = self.paths()
        with patch('rectcropper._batch.ProcessPoolExecutor') as pool:
            results = list(crop_images(paths, output_dir=self.root/'out', **self.options()))
        pool.assert_not_called()
        self.assertEqual([result.input_path for result in results], [path.resolve() for path in paths])
        self.assertEqual(len({result.output_paths[0] for result in results}), 3)
        for result, path in zip(results, paths):
            self.assertIsNone(result.error)
            self.assertEqual(result.crop_points, ((1, 2, 14, 12),))
            expected = crop_image(path, **self.options())[0]
            with Image.open(result.output_paths[0]) as saved:
                np.testing.assert_array_equal(np.array(saved), np.array(expected))

    def test_spawn_workers_preserve_order_and_pixels(self):
        paths = self.paths(2)
        serial = list(crop_images(paths, output_dir=self.root/'serial', **self.options()))
        parallel = list(crop_images(paths, output_dir=self.root/'parallel', workers=2,
                                    max_pending=2, **self.options()))
        self.assertEqual([r.input_path for r in parallel], [path.resolve() for path in paths])
        for one, two in zip(serial, parallel):
            self.assertEqual(one.crop_points, two.crop_points)
            with Image.open(one.output_paths[0]) as a, Image.open(two.output_paths[0]) as b:
                np.testing.assert_array_equal(np.array(a), np.array(b))

    def test_errors_collect_or_propagate(self):
        paths = [self.root/'missing.png'] + self.paths(1)
        for workers in (1, 2):
            results = list(crop_images(paths, output_dir=self.root/f'collect{workers}',
                                       workers=workers, on_error='collect', **self.options()))
            self.assertIn('FileNotFoundError', results[0].error)
            self.assertEqual(results[0].output_paths, ())
            self.assertIsNone(results[1].error)
        with self.assertRaises(FileNotFoundError):
            list(crop_images(paths, output_dir=self.root/'raise', **self.options()))

    def test_input_consumption_is_bounded_and_close_cleans_up(self):
        paths = self.paths(4)
        consumed = []
        executors = []

        class ImmediateExecutor:
            def __init__(self, **kwargs):
                self.closed = False
                executors.append(self)

            def submit(self, function, task):
                future = Future()
                future.set_result(function(task))
                return future

            def shutdown(self, **kwargs):
                self.closed = True

        def inputs():
            for path in paths:
                consumed.append(path)
                yield path

        with patch('rectcropper._batch.ProcessPoolExecutor', ImmediateExecutor):
            results = crop_images(inputs(), output_dir=self.root/'out', workers=2,
                                  max_pending=2, **self.options())
            self.assertEqual(consumed, [])
            next(results)
            self.assertEqual(len(consumed), 2)
            next(results)
            self.assertEqual(len(consumed), 3)
            results.close()
        self.assertTrue(executors[0].closed)

    def test_empty_input_and_invalid_options(self):
        self.assertEqual(list(crop_images([], output_dir=self.root/'empty')), [])
        self.assertFalse((self.root/'empty').exists())
        for options in [dict(workers=0), dict(max_pending=0), dict(on_error='ignore'), dict(output_format='')]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                list(crop_images([], output_dir=self.root/'out', **options))
        for options in [dict(workers=True), dict(workers=1.5), dict(max_pending=True)]:
            with self.subTest(options=options), self.assertRaises(TypeError):
                list(crop_images([], output_dir=self.root/'out', **options))
