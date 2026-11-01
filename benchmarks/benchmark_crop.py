"""Reproducible crop-only benchmark; opening/imports are outside the timer.

python benchmarks/benchmark_crop.py --compare-with /path/to/old/crop.py
"""
import argparse
import importlib.util
import json
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rectanglecropper.crop import RectangleImageCrop


def measure(cropper_type, path, repeats):
    times = []
    boxes = None
    for _ in range(repeats):
        cropper = cropper_type()
        cropper.open(path)
        start = perf_counter()
        cropper.crop(min_crop_width=1, min_crop_height=1, candidate_threshold_group=1)
        times.append(perf_counter() - start)
        current = cropper.get_crop_points()
        if boxes is not None:
            assert current == boxes
        boxes = current
    return median(times), boxes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-with', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    baseline_type = None
    if args.compare_with:
        spec = importlib.util.spec_from_file_location('baseline_crop', args.compare_with)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        baseline_type = module.RectangleImageCrop
    with TemporaryDirectory() as directory:
        for size in (256, 512):
            array = np.full((size, size, 3), 255, dtype=np.uint8)
            array[size//8:size//2, size//8:size//2] = 80
            array[size//2:7*size//8, size//2:7*size//8] = 140
            path = Path(directory) / f'{size}.png'
            Image.fromarray(array).save(path)
            elapsed, boxes = measure(RectangleImageCrop, path, args.repeats)
            result = dict(size=size, repeats=args.repeats, seconds=elapsed, boxes=boxes)
            if baseline_type:
                original, original_boxes = measure(baseline_type, path, args.repeats)
                assert boxes == original_boxes, (boxes, original_boxes)
                result.update(baseline_seconds=original, speedup=original/elapsed)
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
