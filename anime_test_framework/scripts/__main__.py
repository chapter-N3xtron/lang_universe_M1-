#!/usr/bin/env python3
"""
Main entry point for the Anime Test Image Framework.
"""

import argparse
import sys
from pathlib import Path

from utils.config_loader import ConfigLoader
from scripts.anime_generator import AnimeCharacterGenerator
from scripts.image_processor import ImageProcessor
from scripts.batch_generator import BatchGenerator


def generate_single(args):
    """Generate a single character image."""
    config = ConfigLoader()
    generator = AnimeCharacterGenerator(config)
    
    accessories = None
    if args.accessory:
        accessories = [{'type': args.accessory, 'color': args.accessory_color}]
    
    path = generator.generate_and_save(
        args.name,
        hair_color=args.hair_color,
        eye_color=args.eye_color,
        skin_tone=args.skin_tone,
        expression=args.expression,
        hair_style=args.hair_style,
        accessories=accessories,
        include_blush=args.blush,
        width=args.width,
        height=args.height
    )
    
    print(f"Generated: {path}")
    return 0


def generate_batch(args):
    """Generate batch of character images."""
    config = ConfigLoader()
    batch = BatchGenerator(config, max_workers=args.workers)
    
    if args.type == 'expressions':
        paths = batch.generate_expression_variants(
            args.name,
            hair_color=args.hair_color,
            eye_color=args.eye_color
        )
    elif args.type == 'hair':
        paths = batch.generate_hair_color_variants(
            args.name,
            eye_color=args.eye_color,
            hair_color=args.hair_color
        )
    elif args.type == 'eyes':
        paths = batch.generate_eye_color_variants(
            args.name,
            hair_color=args.hair_color,
            eye_color=args.eye_color
        )
    elif args.type == 'accessories':
        paths = batch.generate_accessory_variants(args.name)
    elif args.type == 'all':
        paths = batch.generate_full_combinations(args.name)
    else:
        print(f"Unknown batch type: {args.type}")
        return 1
    
    print(f"Generated {len(paths)} images")
    return 0


def process_image(args):
    """Process an existing image."""
    config = ConfigLoader()
    processor = ImageProcessor(config)
    
    if not Path(args.input).exists():
        print(f"Input file not found: {args.input}")
        return 1
    
    if args.operation == 'resize':
        result = processor.resize_to_preset(args.input, args.preset)
        output = processor.process_and_save(result, args.output)
    elif args.operation == 'blur':
        result = processor.apply_blur(args.input, args.radius)
        output = processor.process_and_save(result, args.output)
    elif args.operation == 'sharpen':
        result = processor.apply_sharpen(args.input, args.factor)
        output = processor.process_and_save(result, args.output)
    elif args.operation == 'grayscale':
        result = processor.apply_grayscale(args.input)
        output = processor.process_and_save(result, args.output)
    elif args.operation == 'sepia':
        result = processor.apply_sepia(args.input)
        output = processor.process_and_save(result, args.output)
    else:
        print(f"Unknown operation: {args.operation}")
        return 1
    
    print(f"Processed: {output}")
    return 0


def validate_image(args):
    """Validate an image file."""
    from utils.image_validator import ImageValidator
    
    validator = ImageValidator()
    results = validator.run_full_validation(
        args.input,
        expected_format=args.format,
        expected_width=args.width,
        expected_height=args.height
    )
    
    print(f"\nValidation Results for: {args.input}")
    print("-" * 40)
    print(f"  Exists: {results['exists']}")
    print(f"  Format: {results['format_valid']}")
    print(f"  Dimensions: {results['dimensions_valid']}")
    print(f"  Color Mode: {results['color_mode_valid']}")
    print(f"  Not Corrupt: {results['not_corrupt']}")
    print(f"  File Size: {results['file_size_valid']}")
    print(f"  Brightness: {results['brightness_valid']}")
    print("-" * 40)
    print(f"  ALL PASSED: {results['all_passed']}")
    
    return 0 if results['all_passed'] else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Anime Character Test Image Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    gen_parser = subparsers.add_parser('generate', help='Generate a single character')
    gen_parser.add_argument('--name', '-n', required=True, help='Output filename')
    gen_parser.add_argument('--hair-color', '-hc', default=None, help='Hair color (hex)')
    gen_parser.add_argument('--eye-color', '-ec', default=None, help='Eye color (hex)')
    gen_parser.add_argument('--skin-tone', '-st', default=None, help='Skin tone (hex)')
    gen_parser.add_argument('--expression', '-e', default='neutral', 
                           choices=['happy', 'sad', 'surprised', 'angry', 'neutral'])
    gen_parser.add_argument('--hair-style', '-hs', default='long',
                           choices=['long', 'short', 'twin_tails', 'bob'])
    gen_parser.add_argument('--accessory', '-a', default=None,
                           choices=['bow', 'glasses', 'cat_ears'])
    gen_parser.add_argument('--accessory-color', '-ac', default='#FF1493')
    gen_parser.add_argument('--blush', '-b', action='store_true')
    gen_parser.add_argument('--width', '-w', type=int, default=512)
    gen_parser.add_argument('--height', '-H', type=int, default=512)
    gen_parser.set_defaults(func=generate_single)
    
    batch_parser = subparsers.add_parser('batch', help='Generate batch of characters')
    batch_parser.add_argument('--name', '-n', required=True, help='Base filename')
    batch_parser.add_argument('--type', '-t', required=True,
                             choices=['expressions', 'hair', 'eyes', 'accessories', 'all'])
    batch_parser.add_argument('--hair-color', '-hc', default='#FFB6C1')
    batch_parser.add_argument('--eye-color', '-ec', default='#4169E1')
    batch_parser.add_argument('--workers', '-w', type=int, default=4)
    batch_parser.set_defaults(func=generate_batch)
    
    proc_parser = subparsers.add_parser('process', help='Process an image')
    proc_parser.add_argument('--input', '-i', required=True, help='Input file')
    proc_parser.add_argument('--output', '-o', required=True, help='Output filename')
    proc_parser.add_argument('--operation', '-op', required=True,
                            choices=['resize', 'blur', 'sharpen', 'grayscale', 'sepia'])
    proc_parser.add_argument('--preset', '-p', default='medium',
                            choices=['thumbnail', 'medium', 'large'])
    proc_parser.add_argument('--radius', '-r', type=float, default=2.0)
    proc_parser.add_argument('--factor', '-f', type=float, default=1.5)
    proc_parser.set_defaults(func=process_image)
    
    val_parser = subparsers.add_parser('validate', help='Validate an image')
    val_parser.add_argument('--input', '-i', required=True, help='Input file')
    val_parser.add_argument('--format', '-f', default='png')
    val_parser.add_argument('--width', '-w', type=int, default=512)
    val_parser.add_argument('--height', '-H', type=int, default=512)
    val_parser.set_defaults(func=validate_image)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
