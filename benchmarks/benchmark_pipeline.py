"""Compare the exact pipeline against a previous package directory.

python benchmarks/benchmark_pipeline.py --baseline /path/to/old/rectcropper
Reports medians plus tracemalloc peaks (not whole-process RSS); import/open
are excluded from detection timings. Rendering+save includes output encoding.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rectcropper


def load_baseline(path):
    spec = importlib.util.spec_from_file_location('_baseline_rectcropper', path/'__init__.py',
                                                submodule_search_locations=[str(path)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def measure(module, path, options, repeats):
    cropper = module.RectangleCropper()
    cropper.open(path)
    cropper.crop(**options)  # warm-up
    times = []
    for _ in range(repeats):
        start = perf_counter()
        cropper.crop(**options)
        times.append(perf_counter()-start)
    tracemalloc.start()
    cropper.crop(**options)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return median(times), peak, cropper


def compare_results(one, two):
    assert one.get_crop_points() == two.get_crop_points()
    np.testing.assert_array_equal(one.get_threshold_pixels(), two.get_threshold_pixels())
    for a, b in zip(one.iter_crops(), two.iter_crops()):
        np.testing.assert_array_equal(np.array(a), np.array(b))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    baseline = load_baseline(args.baseline.resolve())
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = np.full((768, 1024, 3), 255, dtype=np.uint8)
        source[80:650, 80:420] = (30, 80, 150)
        source[180:700, 600:950] = (180, 60, 90)
        rng = np.random.default_rng(42)
        for scene in ('few-objects', 'specks-only', 'objects-and-specks'):
            data = source.copy() if scene != 'specks-only' else np.full_like(source, 255)
            if scene != 'few-objects':
                specks = (rng.random(data.shape[:2]) < .035) & np.all(data == 255, axis=2)
                data[specks] = (30, 80, 150)
            path = root/f'{scene}.png'
            Image.fromarray(data).save(path)
            for mode in ('legacy', 'border'):
                options = dict(background_mode=mode, min_crop_width=1, min_crop_height=1,
                               min_area=10, candidate_threshold_group=1)
                previous, old_peak, old = measure(baseline, path, options, args.repeats)
                current, peak, new = measure(rectcropper, path, options, args.repeats)
                compare_results(old, new)
                print(json.dumps(dict(scene=scene, mode=mode, previous_ms=previous*1000,
                                      current_ms=current*1000, speedup=previous/current,
                                      previous_peak_mib=old_peak/2**20, peak_mib=peak/2**20,
                                      crops=len(new.get_crop_points()))), flush=True)
                # Object-mask pixels must remain identical after label remapping.
                old.crop(**options, output_shape='object')
                new.crop(**options, output_shape='object')
                compare_results(old, new)
        path = root/'few-objects.png'
        results = []
        for name, module in [('previous', baseline), ('current', rectcropper)]:
            times = []
            for _ in range(args.repeats):
                start = perf_counter()
                images = module.crop_image(path, output_dir=root/name, output_shape='object',
                                           min_crop_width=1, min_crop_height=1)
                times.append(perf_counter()-start)
            results.append(images)
            print(json.dumps(dict(scene='render-save-return', implementation=name,
                                  median_ms=median(times)*1000)), flush=True)
        for a, b in zip(*results):
            np.testing.assert_array_equal(np.array(a), np.array(b))


if __name__ == '__main__':
    main()
