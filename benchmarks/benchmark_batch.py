"""Measure serial vs opt-in spawn workers, including open/crop/PNG save/startup.

python benchmarks/benchmark_batch.py --files 12 --size 1536 --workers 2
Small batches may be slower in parallel because every pool starts fresh workers.
"""
import argparse
import json
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rectcropper import crop_images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', type=int, default=12)
    parser.add_argument('--size', type=int, default=1536)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if min(args.files, args.workers, args.repeats) < 1 or args.size < 8:
        parser.error('counts must be positive and size must be at least 8')
    rng = np.random.default_rng(42)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        data = np.full((args.size*3//4, args.size, 3), 255, dtype=np.uint8)
        height, width = data.shape[:2]
        top, bottom = height//8, 7*height//8
        left, right = width//8, 7*width//8
        data[top:bottom, left:right] = rng.integers(
            20, 190, (bottom-top, right-left, 3), dtype=np.uint8)
        paths = []
        for index in range(args.files):
            path = root/f'input{index}.png'
            Image.fromarray(data).save(path)
            paths.append(path)
        reference = None
        for workers in dict.fromkeys((1, args.workers)):
            times = []
            for _ in range(args.repeats):
                start = perf_counter()
                results = list(crop_images(paths, output_dir=root/f'workers{workers}',
                                           workers=workers, min_crop_width=1, min_crop_height=1))
                times.append(perf_counter()-start)
            boxes = [item.crop_points for item in results]
            if reference is None:
                reference = boxes
            assert boxes == reference
            for result in results:
                with Image.open(result.output_paths[0]) as saved:
                    np.testing.assert_array_equal(np.array(saved), data[height//8:7*height//8, width//8:7*width//8])
            print(json.dumps(dict(files=args.files, size=[width, height], workers=workers,
                                  repeats=args.repeats, median_seconds=median(times))), flush=True)


if __name__ == '__main__':
    main()
