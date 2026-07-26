"""
Anime Character Image Generator
Generates cute anime-style character test images using PIL/Pillow.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter
import math
import random

from utils.config_loader import ConfigLoader
from utils.color_utils import ColorUtils


class AnimeCharacterGenerator:
    """Generate anime-style character images."""
    
    def __init__(self, config: Optional[ConfigLoader] = None):
        """
        Initialize the anime character generator.
        
        Args:
            config: Configuration loader instance
        """
        self.config = config or ConfigLoader()
        self.output_paths = self.config.get_output_paths()
        self._ensure_output_dirs()
    
    def _ensure_output_dirs(self):
        """Create output directories if they don't exist."""
        for path in self.output_paths.values():
            path.mkdir(parents=True, exist_ok=True)
    
    def generate_base_face(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        skin_tone: Optional[str] = None
    ) -> Image.Image:
        """
        Generate a base face shape.
        
        Args:
            width: Image width
            height: Image height
            skin_tone: Hex color for skin tone
            
        Returns:
            PIL Image with base face
        """
        width = width or self.config.get('image.default_width', 512)
        height = height or self.config.get('image.default_height', 512)
        skin_tone = skin_tone or self.config.get('character.default_skin_tones.0', '#FFE4C4')
        
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        cx, cy = width // 2, height // 2
        face_width = width * 0.6
        face_height = height * 0.7
        
        face_points = [
            (cx - face_width * 0.3, cy - face_height * 0.4),
            (cx - face_width * 0.5, cy - face_height * 0.1),
            (cx - face_width * 0.45, cy + face_height * 0.3),
            (cx - face_width * 0.3, cy + face_height * 0.5),
            (cx, cy + face_height * 0.55),
            (cx + face_width * 0.3, cy + face_height * 0.5),
            (cx + face_width * 0.45, cy + face_height * 0.3),
            (cx + face_width * 0.5, cy - face_height * 0.1),
            (cx + face_width * 0.3, cy - face_height * 0.4),
        ]
        
        draw.polygon(face_points, fill=skin_tone, outline=self._darken(skin_tone, 0.2))
        
        return img
    
    def generate_eyes(
        self,
        width: int,
        height: int,
        eye_color: str,
        expression: str = 'neutral',
        size_factor: float = 1.0
    ) -> Image.Image:
        """
        Generate anime-style eyes.
        
        Args:
            width: Image width
            height: Image height
            eye_color: Hex color for eyes
            expression: Expression type
            size_factor: Eye size multiplier
            
        Returns:
            PIL Image with eyes
        """
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        cx, cy = width // 2, height // 2
        eye_y = cy - height * 0.05
        eye_spacing = width * 0.15
        eye_width = width * 0.12 * size_factor
        eye_height = height * 0.08 * size_factor
        
        expression_settings = {
            'happy': {'openness': 0.9, 'curve': 0.1},
            'sad': {'openness': 0.6, 'curve': -0.1},
            'surprised': {'openness': 1.2, 'curve': 0},
            'angry': {'openness': 0.5, 'curve': -0.15},
            'neutral': {'openness': 0.75, 'curve': 0}
        }
        
        settings = expression_settings.get(expression, settings['neutral'])
        eye_height *= settings['openness']
        
        for side in [-1, 1]:
            eye_x = cx + side * eye_spacing
            
            white_points = [
                (eye_x - eye_width, eye_y - eye_height * 0.5),
                (eye_x + eye_width, eye_y - eye_height * 0.5),
                (eye_x + eye_width * 0.8, eye_y + eye_height * 0.5),
                (eye_x - eye_width * 0.8, eye_y + eye_height * 0.5),
            ]
            draw.polygon(white_points, fill='white')
            
            pupil_x = eye_x + side * eye_width * 0.2
            pupil_y = eye_y + eye_height * 0.1
            pupil_radius = eye_width * 0.35
            
            draw.ellipse(
                [pupil_x - pupil_radius, pupil_y - pupil_radius,
                 pupil_x + pupil_radius, pupil_y + pupil_radius],
                fill=eye_color
            )
            
            highlight_x = pupil_x - side * pupil_radius * 0.5
            highlight_y = pupil_y - pupil_radius * 0.5
            highlight_radius = pupil_radius * 0.3
            draw.ellipse(
                [highlight_x - highlight_radius, highlight_y - highlight_radius,
                 highlight_x + highlight_radius, highlight_y + highlight_radius],
                fill='white'
            )
            
            eyebrow_y = eye_y - eye_height * 1.5
            eyebrow_start = (eye_x - eye_width * 0.8, eyebrow_y + settings['curve'] * 10)
            eyebrow_end = (eye_x + eye_width * 0.8, eyebrow_y - settings['curve'] * 10)
            draw.line([eyebrow_start, eyebrow_end], fill='#4A4A4A', width=3)
        
        return img
    
    def generate_mouth(
        self,
        width: int,
        height: int,
        expression: str = 'neutral'
    ) -> Image.Image:
        """
        Generate anime-style mouth.
        
        Args:
            width: Image width
            height: Image height
            expression: Expression type
            
        Returns:
            PIL Image with mouth
        """
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        cx, cy = width // 2, height // 2
        mouth_y = cy + height * 0.25
        mouth_width = width * 0.1
        
        mouth_settings = {
            'happy': {'curve': -0.3, 'open': False},
            'sad': {'curve': 0.3, 'open': False},
            'surprised': {'curve': 0, 'open': True},
            'angry': {'curve': 0.2, 'open': False},
            'neutral': {'curve': 0.05, 'open': False}
        }
        
        settings = mouth_settings.get(expression, mouth_settings['neutral'])
        
        if settings['open']:
            draw.ellipse(
                [cx - mouth_width * 0.5, mouth_y - mouth_width * 0.3,
                 cx + mouth_width * 0.5, mouth_y + mouth_width * 0.3],
                fill='#FF6B6B'
            )
        else:
            control_y = mouth_y + settings['curve'] * mouth_width
            draw.arc(
                [cx - mouth_width, mouth_y - mouth_width * 0.5,
                 cx + mouth_width, mouth_y + mouth_width * 0.5],
                0 if settings['curve'] > 0 else 180,
                180 if settings['curve'] > 0 else 360,
                fill='#FF6B6B',
                width=3
            )
        
        return img
    
    def generate_hair(
        self,
        width: int,
        height: int,
        hair_color: str,
        style: str = 'long'
    ) -> Image.Image:
        """
        Generate anime-style hair.
        
        Args:
            width: Image width
            height: Image height
            hair_color: Hex color for hair
            style: Hair style ('long', 'short', 'twin_tails', 'bob')
            
        Returns:
            PIL Image with hair
        """
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        cx, cy = width // 2, height // 2
        dark_color = self._darken(hair_color, 0.3)
        
        if style == 'long':
            hair_points = [
                (cx - width * 0.45, cy - height * 0.4),
                (cx - width * 0.5, cy),
                (cx - width * 0.4, cy + height * 0.4),
                (cx - width * 0.3, cy + height * 0.5),
                (cx + width * 0.3, cy + height * 0.5),
                (cx + width * 0.4, cy + height * 0.4),
                (cx + width * 0.5, cy),
                (cx + width * 0.45, cy - height * 0.4),
                (cx, cy - height * 0.5),
            ]
        elif style == 'short':
            hair_points = [
                (cx - width * 0.45, cy - height * 0.35),
                (cx - width * 0.5, cy - height * 0.1),
                (cx - width * 0.45, cy + height * 0.15),
                (cx + width * 0.45, cy + height * 0.15),
                (cx + width * 0.5, cy - height * 0.1),
                (cx + width * 0.45, cy - height * 0.35),
                (cx, cy - height * 0.45),
            ]
        elif style == 'twin_tails':
            hair_points = [
                (cx - width * 0.45, cy - height * 0.35),
                (cx - width * 0.5, cy - height * 0.1),
                (cx - width * 0.55, cy + height * 0.2),
                (cx - width * 0.5, cy + height * 0.4),
                (cx - width * 0.3, cy + height * 0.15),
                (cx + width * 0.3, cy + height * 0.15),
                (cx + width * 0.5, cy + height * 0.4),
                (cx + width * 0.55, cy + height * 0.2),
                (cx + width * 0.5, cy - height * 0.1),
                (cx + width * 0.45, cy - height * 0.35),
                (cx, cy - height * 0.45),
            ]
        else:
            hair_points = [
                (cx - width * 0.45, cy - height * 0.35),
                (cx - width * 0.5, cy - height * 0.05),
                (cx - width * 0.45, cy + height * 0.2),
                (cx + width * 0.45, cy + height * 0.2),
                (cx + width * 0.5, cy - height * 0.05),
                (cx + width * 0.45, cy - height * 0.35),
                (cx, cy - height * 0.45),
            ]
        
        draw.polygon(hair_points, fill=hair_color, outline=dark_color)
        
        for i in range(3):
            shine_x = cx - width * 0.2 + i * width * 0.15
            shine_y = cy - height * 0.35
            draw.ellipse(
                [shine_x - 5, shine_y - 5, shine_x + 5, shine_y + 5],
                fill=self._lighten(hair_color, 0.4)
            )
        
        return img
    
    def generate_blush(
        self,
        width: int,
        height: int,
        intensity: float = 0.5
    ) -> Image.Image:
        """
        Generate blush marks.
        
        Args:
            width: Image width
            height: Image height
            intensity: Blush intensity (0-1)
            
        Returns:
            PIL Image with blush
        """
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        cx, cy = width // 2, height // 2
        blush_y = cy + height * 0.1
        blush_width = width * 0.08
        blush_height = height * 0.04
        
        alpha = int(255 * intensity * 0.5)
        blush_color = (255, 182, 193, alpha)
        
        for side in [-1, 1]:
            blush_x = cx + side * width * 0.15
            draw.ellipse(
                [blush_x - blush_width, blush_y - blush_height,
                 blush_x + blush_width, blush_y + blush_height],
                fill=blush_color
            )
        
        return img
    
    def generate_accessory(
        self,
        width: int,
        height: int,
        accessory_type: str,
        color: str
    ) -> Image.Image:
        """
        Generate accessory (bow, glasses, cat ears, etc.).
        
        Args:
            width: Image width
            height: Image height
            accessory_type: Type of accessory
            color: Hex color
            
        Returns:
            PIL Image with accessory
        """
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        cx, cy = width // 2, height // 2
        
        if accessory_type == 'bow':
            bow_y = cy - height * 0.45
            bow_size = width * 0.15
            
            draw.polygon([
                (cx - bow_size, bow_y),
                (cx - bow_size * 0.5, bow_y - bow_size * 0.5),
                (cx, bow_y),
                (cx, bow_y + bow_size * 0.3),
            ], fill=color)
            
            draw.polygon([
                (cx + bow_size, bow_y),
                (cx + bow_size * 0.5, bow_y - bow_size * 0.5),
                (cx, bow_y),
                (cx, bow_y + bow_size * 0.3),
            ], fill=color)
            
            draw.ellipse([cx - 10, bow_y - 10, cx + 10, bow_y + 10], fill=self._darken(color, 0.2))
            
        elif accessory_type == 'glasses':
            glass_y = cy - height * 0.05
            glass_width = width * 0.12
            glass_height = height * 0.08
            
            for side in [-1, 1]:
                glass_x = cx + side * width * 0.15
                draw.ellipse(
                    [glass_x - glass_width, glass_y - glass_height,
                     glass_x + glass_width, glass_y + glass_height],
                    outline=color,
                    width=4
                )
            
            draw.line([cx - width * 0.03, glass_y, cx + width * 0.03, glass_y], fill=color, width=4)
            
        elif accessory_type == 'cat_ears':
            ear_y = cy - height * 0.45
            ear_width = width * 0.12
            ear_height = height * 0.15
            
            for side in [-1, 1]:
                ear_x = cx + side * width * 0.25
                inner_color = self._lighten(color, 0.3)
                
                draw.polygon([
                    (ear_x - ear_width, ear_y + ear_height * 0.5),
                    (ear_x, ear_y - ear_height),
                    (ear_x + ear_width, ear_y + ear_height * 0.5),
                ], fill=color)
                
                draw.polygon([
                    (ear_x - ear_width * 0.5, ear_y + ear_height * 0.3),
                    (ear_x, ear_y - ear_height * 0.5),
                    (ear_x + ear_width * 0.5, ear_y + ear_height * 0.3),
                ], fill=inner_color)
        
        return img
    
    def generate_full_character(
        self,
        hair_color: Optional[str] = None,
        eye_color: Optional[str] = None,
        skin_tone: Optional[str] = None,
        expression: str = 'neutral',
        hair_style: str = 'long',
        accessories: Optional[List[Dict]] = None,
        include_blush: bool = False,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> Image.Image:
        """
        Generate a complete anime character image.
        
        Args:
            hair_color: Hex color for hair
            eye_color: Hex color for eyes
            skin_tone: Hex color for skin
            expression: Expression type
            hair_style: Hair style
            accessories: List of accessory dicts
            include_blush: Whether to include blush
            width: Image width
            height: Image height
            
        Returns:
            Complete character PIL Image
        """
        width = width or self.config.get('image.default_width', 512)
        height = height or self.config.get('image.default_height', 512)
        
        hair_color = hair_color or ColorUtils.random_anime_hair_color()
        eye_color = eye_color or ColorUtils.random_anime_eye_color()
        skin_tone = skin_tone or random.choice(self.config.get('character.default_skin_tones', ['#FFE4C4']))
        
        face = self.generate_base_face(width, height, skin_tone)
        hair = self.generate_hair(width, height, hair_color, hair_style)
        eyes = self.generate_eyes(width, height, eye_color, expression)
        mouth = self.generate_mouth(width, height, expression)
        
        composite = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        composite = Image.alpha_composite(composite, face)
        composite = Image.alpha_composite(composite, hair)
        composite = Image.alpha_composite(composite, eyes)
        composite = Image.alpha_composite(composite, mouth)
        
        if include_blush:
            blush = self.generate_blush(width, height, intensity=0.6)
            composite = Image.alpha_composite(composite, blush)
        
        if accessories:
            for acc in accessories:
                acc_img = self.generate_accessory(
                    width, height,
                    acc.get('type', 'bow'),
                    acc.get('color', '#FF1493')
                )
                composite = Image.alpha_composite(composite, acc_img)
        
        return composite
    
    def save_character(
        self,
        image: Image.Image,
        filename: str,
        format: str = 'png',
        subdir: Optional[str] = None
    ) -> Path:
        """
        Save character image to file.
        
        Args:
            image: PIL Image to save
            filename: Output filename
            format: Image format
            subdir: Subdirectory for output
            
        Returns:
            Path to saved file
        """
        if subdir:
            output_dir = self.output_paths['generated'] / subdir
        else:
            output_dir = self.output_paths['generated']
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not filename.endswith(f'.{format}'):
            filename = f'{filename}.{format}'
        
        output_path = output_dir / filename
        
        save_kwargs = {'quality': self.config.get('image.quality', 95)}
        if format.upper() == 'PNG':
            save_kwargs.pop('quality')
        
        image.save(output_path, format=format.upper(), **save_kwargs)
        
        return output_path
    
    def generate_and_save(
        self,
        name: str,
        **kwargs
    ) -> Path:
        """
        Generate and save a character in one step.
        
        Args:
            name: Name for the output file
            **kwargs: Arguments for generate_full_character
            
        Returns:
            Path to saved file
        """
        character = self.generate_full_character(**kwargs)
        return self.save_character(character, name)
    
    def _darken(self, hex_color: str, factor: float) -> str:
        """Darken a hex color."""
        return ColorUtils.darken_color(hex_color, factor)
    
    def _lighten(self, hex_color: str, factor: float) -> str:
        """Lighten a hex color."""
        return ColorUtils.lighten_color(hex_color, factor)
