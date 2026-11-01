# Pipeline performance follow-up

Compared with `6bb4152` (the previous vectorized implementation), not the original
2021 Python pixel traversal. These measurements are fixture-specific results on
Python 3.10/macOS with NumPy 2.2.6, Pillow 12.3.0, and SciPy 1.15.3.

## What changed

1. RGB background matching uses three reusable 2-D boolean buffers, avoiding
   repeated signed RGB difference arrays. Legacy RGB means use exact integer
   rounding and a 256-entry intensity lookup. No downsampling is used.
2. Area filtering can return before bounding-box work if nothing survives. For
   fragmented scenes (at least 256 labels, at most half retained), label IDs are
   compacted before calculating boxes. Other scenes keep the direct path to avoid
   an unnecessary image-wide remap. Object masks and scan order remain intact.
3. `crop_image(output_dir=...)` renders each crop/mask once, saves those images,
   and returns them. JPEG compositing does not mutate returned RGBA images. The
   class `save()` remains streaming, and batch workers also save without retaining
   every cropped image.
4. `crop_images()` adds ordered, bounded serial/process batch execution. Workers
   save results on disk and return only paths/boxes, not large image payloads.

## Detection latency

1024 × 768 images; medians of five warmed crop calls. Opening/importing/saving are
excluded. `min_area=10`, minimum dimensions 1, one background candidate. All
thresholds, boxes, and pixels matched the baseline in rectangle and object modes.

| Scene | Background mode | Previous | Current | Speedup |
| --- | --- | --- | --- | --- |
| Two objects | legacy | 19.75 ms | 13.03 ms | 1.52× |
| Two objects | border | 18.44 ms | 10.20 ms | 1.81× |
| Specks only; all rejected | legacy | 33.96 ms | 10.24 ms | 3.32× |
| Specks only; all rejected | border | 32.59 ms | 7.49 ms | 4.35× |
| Two objects plus specks | legacy | 25.08 ms | 14.40 ms | 1.74× |
| Two objects plus specks | border | 23.53 ms | 11.57 ms | 2.03× |

For two objects in border mode, peak allocations traced *during crop* fell from
14.25 MiB to 9.75 MiB (about 32%). These are `tracemalloc` peaks, not whole-process
RSS; the already opened source image is excluded. Object mode still retains its
component labels as documented.

The combined open/detect/render/PNG-save/return benchmark measured 23.38 ms before
and 13.72 ms after (1.70×). This includes all pipeline changes; it does not isolate
only the duplicate-render fix. A regression test also verifies masks are rendered
once when saving and returning images.

## Batch throughput

Twelve 1536 × 1152 PNG files with a textured rectangular foreground. Median of
three full runs, including process startup, image decode, detection, and PNG
encoding/writes. Serial and process results were checked for matching boxes and
saved pixels.

| Workers | Full batch time |
| --- | --- |
| 1 (serial) | 1.234 s |
| 2 (spawn processes) | 1.032 s |

This workload improved about 1.20× with two workers. Small batches can be slower
in parallel; startup, CPU count, image contents, storage, and worker count all
matter. Each worker has its own source image/arrays, so more workers use more
memory even though the pending queue is bounded.

## Reproduce

Save the previous core and helper in a separate directory, then compare:

```sh
mkdir -p /tmp/rectcropper-before

git show 6bb4152:rectcropper/_core.py > /tmp/rectcropper-before/_core.py
git show 6bb4152:rectcropper/__init__.py > /tmp/rectcropper-before/__init__.py

python benchmarks/benchmark_pipeline.py --baseline /tmp/rectcropper-before
python benchmarks/benchmark_batch.py --files 12 --size 1536 --workers 2 --repeats 3
```

The benchmark checks results before reporting them. Performance can vary between
runs and these results are not general speed guarantees. The sample-image parity
check additionally covered all five existing images at up to 384 × 384, both
background modes, all four shapes, and two area filters: 80 matching cases.
