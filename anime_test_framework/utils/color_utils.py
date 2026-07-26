"""
Color Utilities Module
Provides color manipulation functions for anime character generation.
"""

from typing import Tuple, List, Optional
import colorsys
import random


class ColorUtils:
    """Utility class for color operations."""
    
    @staticmethod
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """
        Convert hex color to RGB tuple.
        
        Args:
            hex_color: Hex color string (e.g., '#FF5733')
            
        Returns:
            RGB tuple (R, G, B)
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    @staticmethod
    def rgb_to_hex(r: int, g: int, b: int) -> str:
        """
        Convert RGB to hex color string.
        
        Args:
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            
        Returns:
            Hex color string
        """
        return f'#{r:02X}{g:02X}{b:02X}'
    
    @staticmethod
    def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
        """
        Convert RGB to HSV.
        
        Args:
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            
        Returns:
            HSV tuple (H, S, V)
        """
        return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    
    @staticmethod
    def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
        """
        Convert HSV to RGB.
        
        Args:
            h: Hue (0-1)
            s: Saturation (0-1)
            v: Value (0-1)
            
        Returns:
            RGB tuple (R, G, B)
        """
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))
    
    @staticmethod
    def lighten_color(hex_color: str, factor: float = 0.1) -> str:
        """
        Lighten a color by a factor.
        
        Args:
            hex_color: Hex color string
            factor: Lightening factor (0-1)
            
        Returns:
            Lightened hex color string
        """
        r, g, b = ColorUtils.hex_to_rgb(hex_color)
        h, s, v = ColorUtils.rgb_to_hsv(r, g, b)
        v = min(1.0, v + factor)
        new_r, new_g, new_b = ColorUtils.hsv_to_rgb(h, s, v)
        return ColorUtils.rgb_to_hex(new_r, new_g, new_b)
    
    @staticmethod
    def darken_color(hex_color: str, factor: float = 0.1) -> str:
        """
        Darken a color by a factor.
        
        Args:
            hex_color: Hex color string
            factor: Darkening factor (0-1)
            
        Returns:
            Darkened hex color string
        """
        r, g, b = ColorUtils.hex_to_rgb(hex_color)
        h, s, v = ColorUtils.rgb_to_hsv(r, g, b)
        v = max(0.0, v - factor)
        new_r, new_g, new_b = ColorUtils.hsv_to_rgb(h, s, v)
        return ColorUtils.rgb_to_hex(new_r, new_g, new_b)
    
    @staticmethod
    def generate_anime_palette(
        base_color: str,
        num_colors: int = 5,
        variation_type: str = 'monochromatic'
    ) -> List[str]:
        """
        Generate an anime-style color palette.
        
        Args:
            base_color: Base hex color
            num_colors: Number of colors to generate
            variation_type: Type of variation ('monochromatic', 'complementary', 'analogous')
            
        Returns:
            List of hex color strings
        """
        r, g, b = ColorUtils.hex_to_rgb(base_color)
        h, s, v = ColorUtils.rgb_to_hsv(r, g, b)
        
        colors = [base_color]
        
        if variation_type == 'monochromatic':
            for i in range(1, num_colors):
                new_v = max(0.2, min(1.0, v + (i - num_colors/2) * 0.15))
                new_r, new_g, new_b = ColorUtils.hsv_to_rgb(h, s, new_v)
                colors.append(ColorUtils.rgb_to_hex(new_r, new_g, new_b))
                
        elif variation_type == 'complementary':
            for i in range(1, num_colors):
                new_h = (h + 0.5 * (i % 2)) % 1.0
                new_r, new_g, new_b = ColorUtils.hsv_to_rgb(new_h, s, v)
                colors.append(ColorUtils.rgb_to_hex(new_r, new_g, new_b))
                
        elif variation_type == 'analogous':
            for i in range(1, num_colors):
                new_h = (h + (i - num_colors/2) * 0.05) % 1.0
                new_r, new_g, new_b = ColorUtils.hsv_to_rgb(new_h, s, v)
                colors.append(ColorUtils.rgb_to_hex(new_r, new_g, new_b))
        
        return colors[:num_colors]
    
    @staticmethod
    def get_skin_tone_variants(base_tone: str) -> List[str]:
        """
        Generate skin tone variants for anime characters.
        
        Args:
            base_tone: Base skin tone hex color
            
        Returns:
            List of skin tone variants (base, lighter, darker, blush)
        """
        return [
            base_tone,
            ColorUtils.lighten_color(base_tone, 0.15),
            ColorUtils.darken_color(base_tone, 0.1),
            '#FFB6C1'  # Blush pink
        ]
    
    @staticmethod
    def random_anime_hair_color() -> str:
        """
        Generate a random anime-style hair color.
        
        Returns:
            Random hex color string
        """
        colors = [
            '#FFB6C1', '#FF69B4', '#FF1493',  # Pinks
            '#87CEEB', '#4169E1', '#00BFFF',  # Blues
            '#DDA0DD', '#9370DB', '#8B00FF',  # Purples
            '#FFD700', '#FFA500', '#FF8C00',  # Golds/Oranges
            '#32CD32', '#228B22', '#006400',  # Greens
            '#C0C0C0', '#708090', '#2F4F4F',  # Silvers/Grays
            '#8B4513', '#A0522D', '#654321',  # Browns
            '#FF0000', '#DC143C', '#B22222',  # Reds
        ]
        return random.choice(colors)
    
    @staticmethod
    def random_anime_eye_color() -> str:
        """
        Generate a random anime-style eye color.
        
        Returns:
            Random hex color string
        """
        colors = [
            '#4169E1', '#00BFFF', '#5F9EA0',  # Blues
            '#32CD32', '#228B22', '#90EE90',  # Greens
            '#FF69B4', '#FF1493', '#FFB6C1',  # Pinks
            '#FFA500', '#FF8C00', '#FFD700',  # Oranges/Golds
            '#9370DB', '#8A2BE2', '#DDA0DD',  # Purples
            '#8B4513', '#A0522D', '#DEB887',  # Browns
            '#FF0000', '#DC143C', '#CD5C5C',  # Reds
        ]
        return random.choice(colors)
