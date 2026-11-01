from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import unittest

from crop_support import CropFixture
from rectcropper import RectangleCropper, crop_image
from rectcropper.__main__ import main
from rectanglecropper.crop import RectangleImageCrop


class ApiTests(CropFixture, unittest.TestCase):
    def test_top_level_class_compatibility(self):
        self.assertIs(RectangleCropper, RectangleImageCrop)
        self.open_array(self.rectangle())
        cropper = RectangleCropper()
        cropper.open(self.root / 'source.png')
        self.assertEqual(self.crop(cropper), [(3, 4, 12, 10)])

    def test_one_call_returns_images_without_files(self):
        self.open_array(self.rectangle())
        images = crop_image(self.root / 'source.png', min_crop_width=1, min_crop_height=1)
        self.assertEqual([image.size for image in images], [(9, 6)])
        self.assertEqual(images[0].getpixel((0, 0)), (100, 100, 100))
        self.assertEqual([path.name for path in self.root.iterdir()], ['source.png'])

    def test_one_call_save_and_options(self):
        self.open_array(self.rectangle())
        output = self.root / 'out'
        images = crop_image(self.root / 'source.png', output_dir=output,
                            output_format='jpg', filename='book', padding=2,
                            min_crop_width=1, min_crop_height=1,
                            background_colors=[(255, 255, 255)])
        self.assertEqual([image.size for image in images], [(13, 10)])
        self.assertTrue((output / 'book_1.jpg').is_file())

    def test_one_call_default_prefix_and_empty_result(self):
        self.open_array(self.rectangle())
        output = self.root / 'out'
        self.assertEqual(crop_image(self.root / 'source.png', output_dir=output), [])
        self.assertEqual(list(output.iterdir()), [])
        crop_image(self.root / 'source.png', output_dir=output,
                   min_crop_width=1, min_crop_height=1)
        self.assertTrue((output / 'source_1.png').is_file())

    def test_command_save_and_summary(self):
        self.open_array(self.rectangle())
        output = self.root / 'out'
        stream = StringIO()
        with redirect_stdout(stream):
            result = main([str(self.root / 'source.png'), '-o', str(output),
                           '--min-width', '1', '--min-height', '1',
                           '--background-color', '255,255,255', '--prefix', 'book'])
        self.assertEqual(result, 0)
        self.assertIn('Saved 1 crop(s)', stream.getvalue())
        self.assertTrue((output / 'book_1.png').is_file())

    def test_command_errors_are_actionable(self):
        for arguments in [[str(self.root / 'missing.png')],
                          [str(self.root / 'source.png'), '--padding', '-1'],
                          [str(self.root / 'source.png'), '--background-color', 'white'],
                          [str(self.root / 'source.png'), '--background-color', '255,0']]:
            self.open_array(self.rectangle())
            stream = StringIO()
            with self.subTest(arguments=arguments), redirect_stderr(stream):
                with self.assertRaises(SystemExit) as error:
                    main(arguments)
                self.assertEqual(error.exception.code, 1)
                self.assertIn('rectcropper:', stream.getvalue())
                self.assertNotIn('Traceback', stream.getvalue())

    def test_module_command_help(self):
        result = subprocess.run([sys.executable, '-m', 'rectcropper', '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--background-color', result.stdout)
