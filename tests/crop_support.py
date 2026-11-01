import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from rectanglecropper.crop import RectangleImageCrop


class CropFixture:
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def open_array(self, array, cropper=None):
        path = self.root / 'source.png'
        Image.fromarray(array.astype(np.uint8)).convert('RGB').save(path)
        cropper = cropper or RectangleImageCrop()
        cropper.open(path)
        return cropper

    def rectangle(self, background=255):
        array = np.full((20, 30), background, dtype=np.uint8)
        array[4:10, 3:12] = 100
        return array

    def crop(self, cropper, **kwargs):
        options = dict(min_crop_width=1, min_crop_height=1,
                       candidate_threshold_group=1)
        options.update(kwargs)
        cropper.crop(**options)
        return cropper.get_crop_points()

