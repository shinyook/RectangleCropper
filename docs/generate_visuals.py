"""Generate README figures from actual rectcropper results (no model assets).

Run from a source checkout: python docs/generate_visuals.py
Requires the package dependencies and a TrueType font (Arial or DejaVu Sans).
"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rectcropper import crop_image

OUT = ROOT / 'docs' / 'images'
OUT.mkdir(parents=True, exist_ok=True)
FONT_PATHS = [Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
              Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
font_path = next((path for path in FONT_PATHS if path.exists()), None)
if font_path is None:
    raise SystemExit('Install Arial or DejaVu Sans to regenerate documentation figures.')


def font(size):
    return ImageFont.truetype(str(font_path), size)


def label(canvas, xy, text, size=22, color='#14273d'):
    ImageDraw.Draw(canvas).text(xy, text, fill=color, font=font(size))


def board(width, height, title, subtitle):
    image = Image.new('RGB', (width, height), '#f1f5fa')
    label(image, (32, 22), title, 34)
    label(image, (32, 70), subtitle, 20, '#50677e')
    return image


def panel(canvas, box, images, caption, preserve_scale=False):
    x, y, width, height = box
    label(canvas, (x, y), caption, 20)
    y += 36
    height -= 36
    tile = Image.new('RGBA', (width, height), 'white')
    d = ImageDraw.Draw(tile)
    for row in range(0, height, 12):
        for col in range(0, width, 12):
            if (row//12 + col//12) % 2:
                d.rectangle((col, row, col+11, row+11), fill='#e5ebf2')
    if images:
        gap = 12
        cell_width = (width - (len(images)+1)*gap)//len(images)
        for index, original in enumerate(images):
            image = original.convert('RGBA')
            max_size = (max(1, cell_width), height-24)
            if not preserve_scale:
                ratio = min(max_size[0]/image.width, max_size[1]/image.height)
                image = image.resize((max(1, round(image.width*ratio)), max(1, round(image.height*ratio))), Image.Resampling.NEAREST)
            else:
                image.thumbnail(max_size, Image.Resampling.NEAREST)
            left = gap + index*(cell_width+gap) + (cell_width-image.width)//2
            top = (height-image.height)//2
            tile.alpha_composite(image, (left, top))
            ImageDraw.Draw(tile).rectangle((left-1, top-1, left+image.width, top+image.height),
                                           outline='#9bacbe', width=1)
    else:
        ImageDraw.Draw(tile).text((24, height//2-14), 'No objects detected', fill='#50677e', font=font(24))
    canvas.paste(tile.convert('RGB'), (x, y))


def extract(image, directory, name, **options):
    path = directory / f'{name}.png'
    image.save(path)
    return crop_image(path, min_crop_width=1, min_crop_height=1, **options)


def main():
    with TemporaryDirectory() as directory:
        directory = Path(directory)
        source = Image.new('RGB', (500, 310), 'white')
        d = ImageDraw.Draw(source)
        d.rectangle((25, 45, 140, 245), fill='#267eb3')
        d.text((43, 80), 'BOOK', fill='#112d48', font=font(22))
        d.line((43, 120, 120, 120), fill='#112d48', width=4)
        d.ellipse((180, 75, 325, 220), fill='#e28936')
        d.ellipse((218, 113, 287, 182), fill='white')
        d.polygon([(365, 65), (405, 65), (405, 190), (475, 190), (475, 240), (365, 240)], fill='#7c65bf')
        objects = extract(source, directory, 'overview', output_shape='object', padding=8)
        assert len(objects) == 3
        hero = board(1320, 500, 'One image. Separate objects.',
                     'Detect the background, find connected objects, and export crops or transparent cutouts.')
        panel(hero, (32, 125, 590, 340), [source], 'INPUT  /  simple background')
        panel(hero, (698, 125, 590, 340), objects, 'OUTPUT  /  three independent RGBA images')
        label(hero, (643, 290), '>', 36, '#267eb3')
        hero.save(OUT/'overview.png')

        shapes = board(1320, 730, 'Choose the output you need.',
                       'Checkerboard = transparency. Each panel below is produced by rectcropper.')
        for col, name in enumerate(['Input', 'Rectangle', 'Object outline', 'Circle', 'Ellipse']):
            label(shapes, (32+col*258, 120), name, 23)
        for row in range(2):
            image = Image.new('RGB', (160, 160), 'white')
            d = ImageDraw.Draw(image)
            if row == 0:
                d.polygon([(20, 25), (55, 25), (55, 90), (140, 90), (140, 125), (20, 125)], fill='#267eb3')
            else:
                d.ellipse((15, 15, 145, 145), fill='#e28936')
                d.ellipse((50, 50, 110, 110), fill='white')
                d.rectangle((73, 73, 87, 87), fill='#7c65bf')
            images = [image] + [extract(image, directory, f'shape-{row}', output_shape=shape, padding=5, min_area=300)[0]
                                for shape in ['rectangle', 'object', 'circle', 'ellipse']]
            for col, result in enumerate(images):
                panel(shapes, (32+col*258, 150+row*270, 230, 256), [result], '')
        shapes.save(OUT/'shape-masks.png')

        controls = board(1320, 1010, 'Control what gets detected and saved.',
                         'Crops are fitted independently; padding panels below use a shared pixel scale.')
        red = Image.new('RGB', (210, 150), (210, 90, 90))
        ImageDraw.Draw(red).rectangle((45, 30, 165, 120), fill=(90, 210, 90))
        legacy = extract(red, directory, 'rgb', background_mode='legacy', candidate_threshold_group=1)
        border = extract(red, directory, 'rgb', background_mode='border')
        assert len(legacy) == 0 and len(border) == 1
        label(controls, (32, 118), '01  Distinguish colors with equal brightness', 24)
        for col, (images, caption) in enumerate([([red], 'Input: red background / green object'), (legacy, 'Legacy RGB mean: 0 objects'), (border, 'RGB border: 1 object')]):
            panel(controls, (32+col*430, 160, 396, 220), images, caption)

        noisy = Image.new('RGB', (210, 150), 'white')
        d = ImageDraw.Draw(noisy)
        d.rectangle((60, 35, 150, 115), fill='#267eb3')
        for x, y in [(15, 15), (185, 20), (20, 125), (185, 125)]:
            d.rectangle((x, y, x+3, y+3), fill='#267eb3')
        unfiltered = extract(noisy, directory, 'noise')
        filtered = extract(noisy, directory, 'noise', min_area=100)
        assert len(unfiltered) == 5 and len(filtered) == 1
        label(controls, (32, 407), '02  Remove small disconnected specks', 24)
        for col, (images, caption) in enumerate([([noisy], 'Input: one object + four specks'), (unfiltered, 'min_area=1: 5 crops'), (filtered, 'min_area=100: 1 crop')]):
            panel(controls, (32+col*430, 449, 396, 220), images, caption)

        tight = extract(noisy, directory, 'padding', min_area=100, output_shape='object', padding=0)
        padded = extract(noisy, directory, 'padding', min_area=100, output_shape='object', padding=20)
        assert tight[0].size == (91, 81) and padded[0].size == (131, 121)
        label(controls, (32, 696), '03  Add transparent space around an object', 24)
        for col, (images, caption) in enumerate([([noisy], 'Same source image'), (tight, 'padding=0: 91 x 81 px'), (padded, 'padding=20: 131 x 121 px')]):
            panel(controls, (32+col*430, 738, 396, 220), images, caption, preserve_scale=True)
        controls.save(OUT/'controls.png')
    print('Generated overview.png, shape-masks.png, controls.png from actual API outputs.')


if __name__ == '__main__':
    main()
