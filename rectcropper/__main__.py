"""Run as either ``rectcropper`` or ``python -m rectcropper``."""
import argparse
from pathlib import Path

from rectcropper import RectangleCropper


def main(argv=None):
    parser = argparse.ArgumentParser(description='Extract rectangular objects from an image.')
    parser.add_argument('image', type=Path, help='source image')
    parser.add_argument('-o', '--output', type=Path, default=Path('crops'), help='output directory (default: crops)')
    parser.add_argument('--min-width', type=int, default=100)
    parser.add_argument('--min-height', type=int, default=100)
    parser.add_argument('--min-area', type=int, default=1)
    parser.add_argument('--padding', type=int, default=0)
    parser.add_argument('--connectivity', type=int, choices=(4, 8), default=4)
    parser.add_argument('--background', choices=('border', 'legacy'), default='border')
    parser.add_argument('--sensitivity', type=int, default=10)
    parser.add_argument('--occupancy-rate', type=int, default=10)
    parser.add_argument('--candidates', type=int, default=3)
    parser.add_argument('--background-color', metavar='R,G,B', action='append',
                        help='explicit RGB background; repeat for multiple colors')
    parser.add_argument('--format', choices=('png', 'jpeg', 'jpg'), default='png')
    parser.add_argument('--shape', choices=('rectangle', 'object', 'circle', 'ellipse'),
                        default='rectangle', help='output mask; PNG preserves transparency')
    parser.add_argument('--prefix', help='output filename prefix (default: input stem)')
    args = parser.parse_args(argv)
    try:
        colors = None
        if args.background_color:
            colors = [tuple(int(channel) for channel in color.split(','))
                      for color in args.background_color]
        cropper = RectangleCropper()
        cropper.open(args.image)
        cropper.crop(min_crop_width=args.min_width, min_crop_height=args.min_height,
                     min_area=args.min_area, padding=args.padding,
                     connectivity=args.connectivity, background_mode=args.background,
                     pixel_sensitivity=args.sensitivity, occupancy_rate=args.occupancy_rate,
                     candidate_threshold_group=args.candidates, background_colors=colors,
                     output_shape=args.shape)
        cropper.save(args.output, args.prefix if args.prefix is not None else args.image.stem, args.format)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'rectcropper: {exc}\n')
    print(f'Saved {len(cropper.get_crop_points())} crop(s) to {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
