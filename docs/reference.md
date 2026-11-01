# rectcropper reference

Detailed options, mask semantics, compatibility notes, and development instructions.

[Back to the visual guide](https://github.com/shinyook/rectcropper#readme)

## Python entry points

```python
from rectcropper import crop_image, RectangleCropper

images = crop_image(
    'input.png',
    output_dir='crops',       # optional: save results as well as returning them
    output_format='png',
    filename='object',        # optional: default is the input filename stem
    background_mode='border',
    min_crop_width=40,
    min_crop_height=40,
)
```

The helper forwards crop options listed below and returns a list of independent
Pillow images. For large result sets, use the class and `iter_crops()` to avoid
holding every output image in memory. `crop_image()`/CLI default to border
background detection; `RectangleCropper.crop()` defaults to legacy detection.

## Command line

```sh
rectcropper input.png -o crops --min-width 40 --min-height 40
rectcropper input.png -o crops --background-color 255,255,255 --min-area 1600
rectcropper input.png -o crops --padding 8 --connectivity 8 --format jpeg
rectcropper input.png -o cutouts --shape object
python -m rectcropper --help
```

Other flags: `--background border|legacy`, `--sensitivity`, `--occupancy-rate`,
`--candidates`, `--prefix`. Repeat `--background-color R,G,B` for multiple colors.
The default output directory is `crops`; the default output format is PNG and
prefix is the input filename stem. Invalid options or unreadable inputs produce a
nonzero exit status. No detected crops is a successful empty result.

## Choose a background mode

| Mode | How it works | When to use it |
| --- | --- | --- |
| `background_mode='legacy'` (default) | Selects common rounded RGB means across the whole image | Preserve existing behavior on simple backgrounds |
| `background_mode='border'` | Selects common RGB colors around the outermost image perimeter | Objects surrounded by a relatively uniform background; colors with equal brightness |
| `background_colors=[(255, 255, 255)]` | Uses explicit RGB colors instead of automatic detection | Background colors are known, or automatic detection is unsuitable |

Border mode groups perimeter colors into 16-level bins and represents each bin
with its actual mean RGB color. It selects up to `candidate_threshold_group`
bins whose share of the perimeter is strictly greater than `occupancy_rate`.
Legacy mode applies that percentage to all image pixels instead.

Explicit colors override automatic detection:

```python
cropper.open('input.png', auto_threshold_detection=False)
cropper.crop(
    background_colors=[(255, 255, 255), (240, 240, 240)],
    pixel_sensitivity=10,
    min_crop_width=40,
    min_crop_height=40,
)
```

Setting `auto_threshold_detection=False` requires `background_colors` on each
`crop()` call. Background color channels must be integers from 0 to 255.

## Crop options

Existing positional arguments retain their order; new options are keyword-only.

| Option | Default | Meaning |
| --- | --- | --- |
| `min_crop_width` | `100` | Minimum component width, inclusive |
| `min_crop_height` | `100` | Minimum component height, inclusive |
| `occupancy_rate` | `10` | Strict background frequency cutoff, integer 1–99 |
| `candidate_threshold_group` | `3` | Maximum number of automatic background candidates |
| `pixel_sensitivity` | `10` | Background tolerance, integer 0–255; 0 means exact matching |
| `background_mode` | `'legacy'` | `'legacy'` or `'border'` |
| `background_colors` | `None` | Nonempty sequence of RGB triples overriding automatic detection |
| `min_area` | `1` | Minimum actual foreground pixels per component |
| `padding` | `0` | Extra pixels on each side, clipped to the image |
| `connectivity` | `4` | `4` for edge neighbors, `8` to include diagonal neighbors |
| `output_shape` | `'rectangle'` | `rectangle`, `object`, `circle`, or `ellipse` |

Dimension and area filters apply **before** padding. Padded boxes may overlap;
components are not merged. In RGB modes, a pixel matches a background color only
when every channel is within `pixel_sensitivity` of that color.

## Transparent cutouts and geometric masks

![Input, rectangle, object outline, circle, and ellipse outputs](https://raw.githubusercontent.com/shinyook/rectcropper/master/docs/images/shape-masks.png)

Checkerboard regions are transparent. In the second row, object mode isolates the
orange ring and excludes the separate purple component inside its bounding box.

Keep the detected object's outline, including its holes, and make the surrounding
background transparent:

```python
from rectcropper import crop_image

images = crop_image(
    'input.png', output_shape='object', output_dir='cutouts',
    min_crop_width=40, min_crop_height=40, padding=8,
)
```

```sh
rectcropper input.png -o cutouts --shape object --min-width 40 --min-height 40
rectcropper input.png -o circles --shape circle
rectcropper input.png -o ellipses --shape ellipse
```

| `output_shape` / `--shape` | Output |
| --- | --- |
| `rectangle` (default) | Original bounding-box crop; existing behavior |
| `object` | RGBA crop containing only that detected connected component |
| `circle` | RGBA crop with a centered circle of diameter `min(width, height)` |
| `ellipse` | RGBA crop with an ellipse filling the crop box |

Masks keep the same rectangular canvas and crop coordinates. Circle/ellipse
geometry is applied to the **padded** crop box and can cut off parts of the object;
these geometric masks do not remove background inside the selected geometry.
Object mode removes background, holes, and other detected components even when
their bounding boxes overlap. Padding around the object is transparent. Existing
source alpha is preserved inside the selected region; masks have hard pixel edges,
without feathering or antialiasing. Use PNG to preserve transparency; JPEG flattens
it onto white.

The class exposes independent, aligned Pillow `L` masks with values 0/255:

```python
from rectcropper import RectangleCropper

cropper = RectangleCropper()
cropper.open('input.png')
cropper.crop(background_mode='border', output_shape='object')
for box, mask, image in zip(cropper.get_crop_points(),
                            cropper.iter_masks(), cropper.iter_crops()):
    print(box, mask.size, image.mode)  # mask selects pixels; image includes source alpha
```

`iter_masks()` reflects the last crop's `output_shape` and excludes original alpha.
Masks/results are reset by `open()` and recomputed by `crop()`. Object mode retains
one image-sized integer component array until the next open/crop; the default and
geometric modes do not retain it. Shape quality still depends on the existing
background-color heuristic, not a learned segmentation model.

## Coordinates and output

- `get_crop_points()` returns a new list of Pillow-style `(left, top, right, bottom)`
  tuples. Right and bottom are exclusive. Results follow the historical scan
  order: each component's leftmost column, then its first foreground row there.
- `get_threshold_pixels()` returns a copy of a NumPy array: intensities in legacy
  mode, or RGB triples in border/manual modes. Call it after `crop()`.
- `open()` applies EXIF orientation and clears previous results. Coordinates refer
  to the oriented image. Every `crop()` recomputes results with the supplied options.
- PNG output retains alpha. JPEG output composites RGBA crops onto white.

Use independent Pillow images directly without saving intermediate files:

```python
for image in cropper.iter_crops():
    print(image.size)
    # Pass image to OCR or other Pillow-compatible processing.
```

## Performance

Version 1.1 replaces Python pixel traversal with vectorized masks and compiled
connected-component labeling. Local crop-only measurements against the corrected
1.0 implementation in commit `b0dca54`:

| Synthetic image | Previous | 1.1 | Speedup |
| --- | --- | --- | --- |
| 256 × 256 | 196.4 ms | 1.76 ms | 111× |
| 512 × 512 | 790.1 ms | 5.79 ms | 137× |

Measurements are medians of three runs on Python 3.10/macOS, using two solid
rectangles on a white background. Both versions returned identical boxes.
Importing, opening, and saving are excluded. These fixture results are not a
guarantee for other images; highly fragmented images have per-component overhead.
SciPy adds installation size and image-sized label storage.

Reproduce the comparison from a source checkout:

```sh
git show b0dca54:rectanglecropper/crop.py > /tmp/rectanglecropper-baseline.py
python benchmarks/benchmark_crop.py --compare-with /tmp/rectanglecropper-baseline.py
```

## Limits and troubleshooting

This is a background-color heuristic, not general-purpose segmentation or
perspective correction. Border mode can be biased by objects covering the
perimeter. Legacy mode can classify a large foreground object as background and
cannot distinguish colors with equal RGB means. Textured backgrounds, shadows,
and gradients may require explicit colors or a different segmentation approach.

Transparency is preserved for output but is not a segmentation signal; detection
uses RGB channels, including colors stored under transparent pixels. Touching
objects form one connected component according to `connectivity`.

If no background candidate exceeds the cutoff, `crop()` raises `RuntimeError`;
lower `occupancy_rate` or set `background_colors`. If there are no foreground
components passing the filters, the result is an empty list. Calling `crop()`
before `open()` raises `RuntimeError`; invalid options raise `TypeError` or
`ValueError`.

## Migrating from RectangleCropper

The new distribution and preferred import package are both named `rectcropper`.
The old `RectangleCropper` project remains a separate PyPI distribution. When
migrating, uninstall it before installing the replacement because both provide
the compatibility `rectanglecropper` module:

```sh
python -m pip uninstall RectangleCropper
python -m pip install --upgrade rectcropper
```

Existing `rectanglecropper.crop.RectangleImageCrop` imports remain supported by a
compatibility shim. New code can use `from rectcropper import crop_image` or
`from rectcropper import RectangleCropper`.

- Python 3.9+ is required. Fixed 2021 dependency pins are replaced with compatible
  NumPy, Pillow, and SciPy ranges.
- Default RGB-mean detection and positional crop arguments remain available.
- Corrected bounds include the final row/column. Minimum dimensions are inclusive.
- Results no longer leak between instances, opened images, or repeated crops.
- Solid/black/multiple background colors no longer trigger the earlier indexing
  and ambiguous-array errors.
- `auto_threshold_detection=False` now requires explicit colors rather than being ignored.
- EXIF orientation is now applied before detection.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check dist/*
```

CI tests minimum dependencies on Python 3.9 and current compatible dependencies
on Python 3.10/3.13, including installed-package imports outside the checkout.
Tests cover background selection, component bounds/order, independent random-mask
connectivity checks, output pixels, EXIF orientation, and repeated operations.

Releases use `.github/workflows/release.yml`: tests and builds run before uploading
the wheel and source distribution through PyPI Trusted Publishing. Under PyPI
account `shin6`, the publisher for project `rectcropper` must be registered for GitHub owner `shinyook`, repository `rectcropper`, workflow
`release.yml`, environment `pypi`. A published GitHub release triggers deployment;
the manual workflow accepts a version tag for retries.

## License

[MIT](https://github.com/shinyook/rectcropper/blob/master/LICENSE). Report reproducible bugs through
[GitHub Issues](https://github.com/shinyook/rectcropper/issues).
