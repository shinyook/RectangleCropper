"""Background-based rectangle extraction with vectorized connected components."""
from pathlib import Path
import warnings

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage


class ImageThresholdUtil:
    @staticmethod
    def get_threshold_pixels(row, col, image, rep_count, target_rate):
        """Return the most frequent intensities exceeding target_rate percent."""
        # Rounded RGB means are integers in [0, 255]; a histogram avoids sorting
        # every pixel and preserves the previous stable tie-breaking order.
        counts = np.bincount(np.asarray(image, dtype=np.uint8).ravel(), minlength=256)
        values = np.flatnonzero(counts)
        candidates = values[np.argsort(counts[values], kind='stable')[-rep_count:]]
        return candidates[counts[candidates] / (row * col) * 100 > target_rate]


class RectangleImageCrop:
    """Extract connected foreground regions, returning Pillow crop boxes.

    The default ``background_mode='legacy'`` retains RGB-mean detection.
    ``'border'`` estimates RGB background colors from the outermost pixels,
    keeping similarly bright but differently colored foregrounds distinct.
    """

    def __init__(self):
        self.__img = None
        self.__rgb = None
        self.__threshold_pixels = None
        self.__save_points = []
        self.__auto_threshold_detection = True

    def open(self, image_path, auto_threshold_detection=True) -> None:
        """Open an image, apply EXIF orientation, and clear previous results.

        With auto_threshold_detection=False, crop() requires background_colors.
        Coordinates refer to the oriented image. Transparency is preserved in
        output, but background detection uses the image's RGB channels.
        """
        with Image.open(image_path) as image:
            oriented = ImageOps.exif_transpose(image)
            self.__img = oriented.convert('RGBA' if 'A' in oriented.getbands()
                                          or 'transparency' in oriented.info else 'RGB')
        self.__rgb = np.asarray(self.__img.convert('RGB'))
        self.__save_points = []
        self.__threshold_pixels = None
        self.__auto_threshold_detection = auto_threshold_detection

    @staticmethod
    def __integer(name, value, minimum=1, maximum=None):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise TypeError(f'{name} must be an integer')
        if value < minimum or (maximum is not None and value > maximum):
            raise ValueError(f'{name} must be >= {minimum}' +
                             (f' and <= {maximum}' if maximum is not None else ''))

    def __border_colors(self, candidate_count, occupancy_rate):
        height, width = self.__rgb.shape[:2]
        # Every perimeter pixel appears exactly once, including 1-pixel images.
        if height == 1:
            border = self.__rgb[0]
        elif width == 1:
            border = self.__rgb[:, 0]
        else:
            border = np.concatenate((self.__rgb[0], self.__rgb[-1],
                                     self.__rgb[1:-1, 0], self.__rgb[1:-1, -1]))
        # Quantize only the perimeter into 16-level RGB bins to group small
        # variations; represent each bin with its actual mean RGB value.
        quantized = border.astype(np.int32) // 16
        keys = quantized[:, 0] * 256 + quantized[:, 1] * 16 + quantized[:, 2]
        counts = np.bincount(keys, minlength=4096)
        occupied = np.flatnonzero(counts)
        candidates = occupied[np.argsort(counts[occupied], kind='stable')[-candidate_count:]]
        candidates = candidates[counts[candidates] / len(border) * 100 > occupancy_rate]
        channels = [np.bincount(keys, weights=border[:, channel], minlength=4096)
                    for channel in range(3)]
        sums = np.stack(channels, axis=1)
        return np.rint(sums[candidates] / counts[candidates, None]).astype(np.int16)

    def crop(self, min_crop_width=100, min_crop_height=100, occupancy_rate=10,
             candidate_threshold_group=3, pixel_sensitivity=10, *,
             background_mode='legacy', background_colors=None, min_area=1,
             padding=0, connectivity=4):
        """Detect foreground and store rectangles in historical left-to-right order.

        background_mode: 'legacy' (global RGB mean histogram) or 'border' (RGB
            colors on the perimeter, grouped into 16-level bins). occupancy_rate
            is a strict percentage cutoff, over all pixels or perimeter pixels
            respectively; it must be below 100.
        background_colors: optional sequence of RGB triples in [0, 255],
            overriding automatic detection. A pixel is background if every
            channel differs by at most pixel_sensitivity from any supplied color.
        min_area: minimum number of actual foreground pixels per component.
        padding: pixels added on all sides, clipped to image boundaries.
        connectivity: 4 for edge neighbors, 8 to include diagonal neighbors.

        Minimum width/height and area are tested before padding. Existing
        positional arguments keep their original meaning. No file is written.
        """
        for name, value in [('min_crop_width', min_crop_width),
                            ('min_crop_height', min_crop_height),
                            ('candidate_threshold_group', candidate_threshold_group),
                            ('min_area', min_area)]:
            self.__integer(name, value)
        self.__integer('occupancy_rate', occupancy_rate, 1, 99)
        self.__integer('pixel_sensitivity', pixel_sensitivity, 0, 255)
        self.__integer('padding', padding, 0)
        self.__integer('connectivity', connectivity, 4, 8)
        if connectivity not in (4, 8):
            raise ValueError('connectivity must be 4 or 8')
        if background_mode not in ('legacy', 'border'):
            raise ValueError("background_mode must be 'legacy' or 'border'")
        colors = None
        if background_colors is not None:
            colors = np.asarray(background_colors)
            if (colors.ndim != 2 or colors.shape[1] != 3 or len(colors) == 0
                    or not np.issubdtype(colors.dtype, np.number)
                    or np.iscomplexobj(colors)):
                raise ValueError('background_colors must be a nonempty sequence of RGB triples')
            if not np.all(np.isfinite(colors)) or np.any((colors < 0) | (colors > 255)):
                raise ValueError('background_colors channels must be finite values in [0, 255]')
            if np.any(colors != np.rint(colors)):
                raise ValueError('background_colors channels must be integers')
            colors = colors.astype(np.int16)
        if self.__img is None:
            raise RuntimeError('open method must be called before crop.')
        if colors is None and not self.__auto_threshold_detection:
            raise ValueError('background_colors is required when auto_threshold_detection=False')
        if occupancy_rate < 7:
            warnings.warn('occupancy_rate is too low. More background candidates may be included.')
        if candidate_threshold_group > 5:
            warnings.warn('candidate_threshold_group is too large. More colors may be classified as background.')
        if pixel_sensitivity > 10 or pixel_sensitivity < 5:
            warnings.warn('pixel_sensitivity is outside the recommended range of 5 to 10.')

        self.__save_points = []
        self.__threshold_pixels = None
        height, width = self.__rgb.shape[:2]
        if colors is None and background_mode == 'legacy':
            intensity = np.rint(self.__rgb.mean(axis=2)).astype(np.uint8)
            thresholds = ImageThresholdUtil.get_threshold_pixels(
                width, height, intensity, candidate_threshold_group, occupancy_rate)
            foreground = np.ones((height, width), dtype=bool)
            intensity = intensity.astype(np.int16)
            for value in thresholds:
                foreground &= np.abs(intensity - int(value)) > pixel_sensitivity
        else:
            thresholds = colors if colors is not None else self.__border_colors(
                candidate_threshold_group, occupancy_rate)
            foreground = np.ones((height, width), dtype=bool)
            rgb = self.__rgb.astype(np.int16)
            for color in thresholds:
                foreground &= np.any(np.abs(rgb - color) > pixel_sensitivity, axis=2)
        self.__threshold_pixels = thresholds
        if len(thresholds) == 0:
            raise RuntimeError('threshold pixels are empty. No threshold pixels were detected. '
                               'drop a occupancy_rate value or provide background_colors')

        structure = ndimage.generate_binary_structure(2, 1 if connectivity == 4 else 2)
        labels, count = ndimage.label(foreground, structure=structure)
        areas = np.bincount(labels.ravel(), minlength=count + 1) if min_area > 1 else None
        results = []
        for label, region in enumerate(ndimage.find_objects(labels, max_label=count), 1):
            rows, cols = region
            if cols.stop - cols.start < min_crop_width or rows.stop - rows.start < min_crop_height:
                continue
            if areas is not None and areas[label] < min_area:
                continue
            first_row = rows.start + np.flatnonzero(labels[rows, cols.start] == label)[0]
            box = (max(0, cols.start - padding), max(0, rows.start - padding),
                   min(width, cols.stop + padding), min(height, rows.stop + padding))
            results.append(((cols.start, int(first_row)), box))
        self.__save_points = [box for _, box in sorted(results)]

    def iter_crops(self):
        """Yield independent Pillow images without saving all crops to disk."""
        if self.__img is None:
            raise RuntimeError('open method must be called before iter_crops.')
        for box in self.__save_points:
            yield self.__img.crop(box)

    def save(self, saved_path, filename, saved_format) -> None:
        """Save crops as filename_1.ext, creating the output directory if needed.

        RGBA crops saved as JPEG are composited onto white.
        """
        directory = Path(saved_path)
        directory.mkdir(parents=True, exist_ok=True)
        image_format = saved_format.upper()
        if image_format == 'JPG':
            image_format = 'JPEG'
        for idx, image in enumerate(self.iter_crops(), 1):
            if image_format == 'JPEG' and image.mode == 'RGBA':
                background = Image.new('RGB', image.size, 'white')
                background.paste(image, mask=image.getchannel('A'))
                image = background
            image.save(directory / f'{filename}_{idx}.{saved_format.lower()}', format=image_format)

    def get_threshold_pixels(self):
        """Return a copy of detected intensities, or RGB triples in RGB modes."""
        if self.__threshold_pixels is None:
            raise RuntimeError('threshold pixels are None. crop method must be done before this method.')
        return self.__threshold_pixels.copy()

    def get_crop_points(self) -> list:
        """Return (left, top, right, bottom) boxes; right/bottom are exclusive."""
        return list(self.__save_points)
