# rectcropper

**Find objects on simple backgrounds. Save separate crops or transparent cutouts.**

[![PyPI](https://img.shields.io/pypi/v/rectcropper.svg)](https://pypi.org/project/rectcropper/)
[![Tests](https://github.com/shinyook/rectcropper/actions/workflows/tests.yml/badge.svg)](https://github.com/shinyook/rectcropper/actions/workflows/tests.yml)
[![Python](https://img.shields.io/pypi/pyversions/rectcropper.svg)](https://pypi.org/project/rectcropper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/shinyook/rectcropper/blob/master/LICENSE)

![One input image becomes three independent object cutouts](https://raw.githubusercontent.com/shinyook/rectcropper/master/docs/images/overview.png)

A small Python library and command line tool built on NumPy, Pillow, and SciPy.
No model downloads or training. Best for product images, simple graphics, and
objects surrounded by relatively uniform background colors.

[Get started](#get-started) · [Output shapes](#choose-an-output-shape) ·
[Detection controls](#control-detection-and-spacing) ·
[Full reference](https://github.com/shinyook/rectcropper/blob/master/docs/reference.md)

> **Release status:** PyPI **1.2.0** includes rectangular crops and detection
> controls. Transparent object, circle, and ellipse output is merged on `master`
> and awaits the next release. Install the latest source below to use those modes.

## Get started

Python **3.9+** is required. Dependencies are installed automatically.

```sh
# Latest published package
python -m pip install --upgrade rectcropper

# Latest source, including transparent shape output
python -m pip install --upgrade "git+https://github.com/shinyook/rectcropper.git"
```

Crop from the command line:

```sh
rectcropper input.png -o crops --min-width 40 --min-height 40
```

Or use one Python call. The result is a list of independent Pillow images:

```python
from rectcropper import crop_image

images = crop_image('input.png', min_crop_width=40, min_crop_height=40)
```

Add `output_dir='crops'` to save files too. Output directories are created
automatically; the default names are `input_1.png`, `input_2.png`, and so on.
Matching filenames are overwritten; unrelated or leftover files are not removed.

The helper and CLI use **RGB border detection** by default. Minimum width and
height default to **100 × 100**; lower them for smaller objects, as shown above.

## Choose an output shape

![Actual inputs and rectangle, object outline, circle, and ellipse outputs](https://raw.githubusercontent.com/shinyook/rectcropper/master/docs/images/shape-masks.png)

**Checkerboard means transparency.** Thin outlines mark each image's canvas.
The ring example shows why a shape mask is useful: `object` removes the white
hole and excludes the separate purple object inside the ring's bounding box.

| Output | What it does | Python option / CLI flag |
| --- | --- | --- |
| Rectangle | Keeps the original contents of each bounding box | Default |
| Object outline | Keeps only that detected component; background and holes become transparent | `output_shape='object'` / `--shape object` |
| Circle | Applies a centered circle to the crop | `output_shape='circle'` / `--shape circle` |
| Ellipse | Applies an ellipse that fills the crop box | `output_shape='ellipse'` / `--shape ellipse` |

Transparent modes require the latest source until the next PyPI release:

```python
images = crop_image(
    'input.png',
    output_shape='object',
    output_dir='cutouts',
    min_crop_width=40,
    min_crop_height=40,
    padding=8,
)
```

```sh
rectcropper input.png -o cutouts --shape object --min-width 40 --min-height 40
```

All output files still have rectangular canvases. Circle/ellipse masks cut away
parts outside their geometry; they do not remove background inside it. Use **PNG**
to retain transparency. JPEG flattens it onto white. Masks have hard pixel edges,
and preserve existing source alpha inside the selected region.

## Control detection and spacing

![RGB background detection, foreground area filtering, and transparent padding compared using actual outputs](https://raw.githubusercontent.com/shinyook/rectcropper/master/docs/images/controls.png)

| Goal | Option | Effect |
| --- | --- | --- |
| Distinguish different colors with equal brightness | `background_mode='border'` | Estimates RGB background colors from the image perimeter |
| Use a known background | `background_colors=[(255, 255, 255)]` | Overrides automatic background selection |
| Ignore tiny specks | `min_area=100` | Rejects components with fewer than 100 actual foreground pixels |
| Add space around a crop | `padding=20` | Adds up to 20 pixels per side, clipped to the input boundary |
| Group diagonal neighbors | `connectivity=8` | Joins diagonal pixels; the default `4` joins edge neighbors only |
| Adjust background tolerance | `pixel_sensitivity=5` | Sets the allowed color difference; `0` means exact matching |

Width, height, and area filters apply **before padding**. Object-mode padding is
transparent; default rectangle padding keeps the original image pixels. Padded
boxes can overlap and are not merged. Crops are fitted independently in the
figures; the padding comparison uses the same pixel scale and shows canvas borders.

## Need coordinates or masks?

Use the class directly for repeated calls, metadata, or processing one crop at a
time. Its default detection mode is `legacy`; choose `border` to match the helper.

```python
from rectcropper import RectangleCropper

cropper = RectangleCropper()
cropper.open('input.png')
cropper.crop(background_mode='border', output_shape='object')

for box, mask, image in zip(cropper.get_crop_points(),
                            cropper.iter_masks(), cropper.iter_crops()):
    print(box, mask.size, image.mode)
```

Boxes use `(left, top, right, bottom)` with exclusive right/bottom edges. Masks
are independent Pillow `L` images containing 0/255 selection values; cropped RGBA
images also preserve source alpha. EXIF orientation is applied before detection.
Object mode retains an image-sized component label array until the next open/crop.

## Performance and limits

The vectorized engine measured **111–137× faster** than the corrected earlier
Python traversal on two synthetic fixtures. These are crop-only medians of three
runs on Python 3.10/macOS, with matching boxes; import/open/save times are excluded.
They are not speed guarantees for other inputs.
[Benchmark details and reproduction](https://github.com/shinyook/rectcropper/blob/master/docs/reference.md#performance).

This is a background-color heuristic, **not general-purpose segmentation or
perspective correction**. Textured backgrounds, shadows, gradients, and objects
covering the perimeter can defeat automatic detection. Transparency is preserved
in output but is not used as a segmentation signal. Touching objects may form one
component, and geometric masks can cut off parts of an object.

## More documentation

- [Complete option reference and CLI usage](https://github.com/shinyook/rectcropper/blob/master/docs/reference.md)
- [Migrating from RectangleCropper](https://github.com/shinyook/rectcropper/blob/master/docs/reference.md#migrating-from-rectanglecropper): uninstall the old distribution before installing rectcropper, because both provide the compatibility module.
- [Development, tests, and releases](https://github.com/shinyook/rectcropper/blob/master/docs/reference.md#development)
- [Report a reproducible issue](https://github.com/shinyook/rectcropper/issues)

The figures are generated from actual API outputs, including assertions for object
counts and crop dimensions. Regenerate them with:

```sh
python docs/generate_visuals.py
```

[MIT license](https://github.com/shinyook/rectcropper/blob/master/LICENSE).
