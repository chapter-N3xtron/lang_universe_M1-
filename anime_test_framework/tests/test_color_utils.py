"""
Test suite for ColorUtils
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.color_utils import ColorUtils


class TestColorUtils:
    """Test cases for color utilities."""
    
    def test_hex_to_rgb(self):
        """Test hex to RGB conversion."""
        rgb = ColorUtils.hex_to_rgb('#FF5733')
        assert rgb == (255, 87, 51)
    
    def test_hex_to_rgb_no_hash(self):
        """Test hex to RGB without hash prefix."""
        rgb = ColorUtils.hex_to_rgb('FF5733')
        assert rgb == (255, 87, 51)
    
    def test_rgb_to_hex(self):
        """Test RGB to hex conversion."""
        hex_color = ColorUtils.rgb_to_hex(255, 87, 51)
        assert hex_color == '#FF5733'
    
    def test_rgb_to_hsv(self):
        """Test RGB to HSV conversion."""
        hsv = ColorUtils.rgb_to_hsv(255, 0, 0)
        assert hsv[0] == 0.0
        assert hsv[1] == 1.0
        assert hsv[2] == 1.0
    
    def test_hsv_to_rgb(self):
        """Test HSV to RGB conversion."""
        rgb = ColorUtils.hsv_to_rgb(0.0, 1.0, 1.0)
        assert rgb == (255, 0, 0)
    
    def test_lighten_color(self):
        """Test color lightening."""
        original = '#808080'
        lighter = ColorUtils.lighten_color(original, 0.2)
        
        assert lighter.startswith('#')
        assert len(lighter) == 7
    
    def test_darken_color(self):
        """Test color darkening."""
        original = '#808080'
        darker = ColorUtils.darken_color(original, 0.2)
        
        assert darker.startswith('#')
        assert len(darker) == 7
    
    def test_lighten_then_darken(self):
        """Test lightening then darkening returns close to original."""
        original = '#808080'
        lighter = ColorUtils.lighten_color(original, 0.1)
        back = ColorUtils.darken_color(lighter, 0.1)
        
        assert back.startswith('#')
    
    def test_generate_monochromatic_palette(self):
        """Test monochromatic palette generation."""
        palette = ColorUtils.generate_anime_palette(
            '#4169E1',
            num_colors=5,
            variation_type='monochromatic'
        )
        
        assert len(palette) == 5
        assert palette[0] == '#4169E1'
        assert all(c.startswith('#') for c in palette)
    
    def test_generate_complementary_palette(self):
        """Test complementary palette generation."""
        palette = ColorUtils.generate_anime_palette(
            '#4169E1',
            num_colors=4,
            variation_type='complementary'
        )
        
        assert len(palette) == 4
        assert all(c.startswith('#') for c in palette)
    
    def test_generate_analogous_palette(self):
        """Test analogous palette generation."""
        palette = ColorUtils.generate_anime_palette(
            '#4169E1',
            num_colors=5,
            variation_type='analogous'
        )
        
        assert len(palette) == 5
        assert all(c.startswith('#') for c in palette)
    
    def test_get_skin_tone_variants(self):
        """Test skin tone variant generation."""
        base_tone = '#FFE4C4'
        variants = ColorUtils.get_skin_tone_variants(base_tone)
        
        assert len(variants) == 4
        assert variants[0] == base_tone
        assert all(v.startswith('#') for v in variants)
    
    def test_random_anime_hair_color(self):
        """Test random hair color generation."""
        color = ColorUtils.random_anime_hair_color()
        
        assert color.startswith('#')
        assert len(color) == 7
    
    def test_random_anime_hair_color_variety(self):
        """Test that random hair colors have variety."""
        colors = set()
        for _ in range(20):
            colors.add(ColorUtils.random_anime_hair_color())
        
        assert len(colors) > 1
    
    def test_random_anime_eye_color(self):
        """Test random eye color generation."""
        color = ColorUtils.random_anime_eye_color()
        
        assert color.startswith('#')
        assert len(color) == 7
    
    def test_random_anime_eye_color_variety(self):
        """Test that random eye colors have variety."""
        colors = set()
        for _ in range(20):
            colors.add(ColorUtils.random_anime_eye_color())
        
        assert len(colors) > 1
    
    def test_hex_to_rgb_lowercase(self):
        """Test hex to RGB with lowercase hex."""
        rgb = ColorUtils.hex_to_rgb('#ff5733')
        assert rgb == (255, 87, 51)
    
    def test_rgb_to_hex_roundtrip(self):
        """Test RGB to hex roundtrip conversion."""
        original = '#AABBCC'
        rgb = ColorUtils.hex_to_rgb(original)
        back = ColorUtils.rgb_to_hex(*rgb)
        assert back == original
