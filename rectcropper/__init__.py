"""Simple entry points for rectangular image cropping."""
from pathlib import Path

from ._core import RectangleImageCrop

RectangleCropper = RectangleImageCrop
__all__ = ['RectangleCropper', 'RectangleImageCrop', 'crop_image']


def crop_image(image_path, *, output_dir=None, output_format='png', filename=None,
               **options):
    """Return a list of independent Pillow crops, optionally saving them.

    Uses RGB border detection by default. All crop() options, including size
    filters, padding, output_shape, and explicit background colors, can be passed
    directly. Nonrectangular output is RGBA; PNG preserves its transparency.
    Coordinates and detected thresholds are available through RectangleCropper
    when more control is needed. Existing files with matching names are replaced.
    """
    options.setdefault('background_mode', 'border')
    cropper = RectangleCropper()
    cropper.open(image_path)
    cropper.crop(**options)
    if output_dir is not None:
        cropper.save(output_dir, filename if filename is not None else Path(image_path).stem,
                     output_format)
    return list(cropper.iter_crops())
