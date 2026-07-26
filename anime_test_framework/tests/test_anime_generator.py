"""
Test suite for AnimeCharacterGenerator
"""

import pytest
from pathlib import Path
from PIL import Image
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.anime_generator import AnimeCharacterGenerator
from utils.config_loader import ConfigLoader


class TestAnimeCharacterGenerator:
    """Test cases for the anime character generator."""
    
    @pytest.fixture
    def generator(self):
        """Create a generator instance for testing."""
        config = ConfigLoader()
        return AnimeCharacterGenerator(config)
    
    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """Create temporary output directory."""
        return tmp_path / 'images'
    
    def test_init(self, generator):
        """Test generator initialization."""
        assert generator is not None
        assert generator.config is not None
        assert generator.output_paths is not None
    
    def test_generate_base_face(self, generator):
        """Test base face generation."""
        face = generator.generate_base_face(width=256, height=256)
        
        assert isinstance(face, Image.Image)
        assert face.size == (256, 256)
        assert face.mode == 'RGBA'
    
    def test_generate_base_face_default_size(self, generator):
        """Test base face with default dimensions."""
        face = generator.generate_base_face()
        
        expected_width = generator.config.get('image.default_width', 512)
        expected_height = generator.config.get('image.default_height', 512)
        
        assert face.size == (expected_width, expected_height)
    
    def test_generate_eyes(self, generator):
        """Test eye generation."""
        eyes = generator.generate_eyes(
            width=512,
            height=512,
            eye_color='#4169E1',
            expression='happy'
        )
        
        assert isinstance(eyes, Image.Image)
        assert eyes.size == (512, 512)
        assert eyes.mode == 'RGBA'
    
    def test_generate_eyes_all_expressions(self, generator):
        """Test eye generation with all expressions."""
        expressions = ['happy', 'sad', 'surprised', 'angry', 'neutral']
        
        for expr in expressions:
            eyes = generator.generate_eyes(512, 512, '#4169E1', expr)
            assert eyes is not None
            assert eyes.size == (512, 512)
    
    def test_generate_mouth(self, generator):
        """Test mouth generation."""
        mouth = generator.generate_mouth(
            width=512,
            height=512,
            expression='happy'
        )
        
        assert isinstance(mouth, Image.Image)
        assert mouth.size == (512, 512)
        assert mouth.mode == 'RGBA'
    
    def test_generate_hair(self, generator):
        """Test hair generation."""
        hair_styles = ['long', 'short', 'twin_tails', 'bob']
        
        for style in hair_styles:
            hair = generator.generate_hair(
                width=512,
                height=512,
                hair_color='#FFB6C1',
                style=style
            )
            
            assert isinstance(hair, Image.Image)
            assert hair.size == (512, 512)
    
    def test_generate_blush(self, generator):
        """Test blush generation."""
        blush = generator.generate_blush(
            width=512,
            height=512,
            intensity=0.5
        )
        
        assert isinstance(blush, Image.Image)
        assert blush.size == (512, 512)
        assert blush.mode == 'RGBA'
    
    def test_generate_accessory_bow(self, generator):
        """Test bow accessory generation."""
        accessory = generator.generate_accessory(
            width=512,
            height=512,
            accessory_type='bow',
            color='#FF1493'
        )
        
        assert isinstance(accessory, Image.Image)
        assert accessory.size == (512, 512)
    
    def test_generate_accessory_glasses(self, generator):
        """Test glasses accessory generation."""
        accessory = generator.generate_accessory(
            width=512,
            height=512,
            accessory_type='glasses',
            color='#000000'
        )
        
        assert isinstance(accessory, Image.Image)
        assert accessory.size == (512, 512)
    
    def test_generate_accessory_cat_ears(self, generator):
        """Test cat ears accessory generation."""
        accessory = generator.generate_accessory(
            width=512,
            height=512,
            accessory_type='cat_ears',
            color='#FFB6C1'
        )
        
        assert isinstance(accessory, Image.Image)
        assert accessory.size == (512, 512)
    
    def test_generate_full_character(self, generator):
        """Test full character generation."""
        character = generator.generate_full_character(
            hair_color='#FFB6C1',
            eye_color='#4169E1',
            skin_tone='#FFE4C4',
            expression='happy',
            hair_style='long',
            include_blush=True
        )
        
        assert isinstance(character, Image.Image)
        assert character.size[0] == generator.config.get('image.default_width', 512)
        assert character.size[1] == generator.config.get('image.default_height', 512)
        assert character.mode == 'RGBA'
    
    def test_generate_full_character_random_colors(self, generator):
        """Test character generation with random colors."""
        character = generator.generate_full_character()
        
        assert isinstance(character, Image.Image)
        assert character.mode == 'RGBA'
    
    def test_save_character(self, generator, temp_output_dir):
        """Test saving character image."""
        character = generator.generate_full_character()
        generator.output_paths['generated'] = temp_output_dir
        
        saved_path = generator.save_character(character, 'test_character', 'png')
        
        assert saved_path.exists()
        assert saved_path.suffix == '.png'
        
        with Image.open(saved_path) as img:
            assert img.format == 'PNG'
    
    def test_save_character_jpg(self, generator, temp_output_dir):
        """Test saving character as JPG."""
        character = generator.generate_full_character()
        generator.output_paths['generated'] = temp_output_dir
        
        saved_path = generator.save_character(character, 'test_character', 'jpg')
        
        assert saved_path.exists()
        assert saved_path.suffix == '.jpg'
    
    def test_generate_and_save(self, generator, temp_output_dir):
        """Test generate and save in one step."""
        generator.output_paths['generated'] = temp_output_dir
        
        saved_path = generator.generate_and_save(
            'test_char',
            hair_color='#FFB6C1',
            eye_color='#4169E1',
            expression='happy'
        )
        
        assert saved_path.exists()
        assert saved_path.is_file()
    
    def test_generate_character_with_accessories(self, generator):
        """Test character generation with accessories."""
        accessories = [
            {'type': 'bow', 'color': '#FF1493'},
            {'type': 'glasses', 'color': '#000000'}
        ]
        
        character = generator.generate_full_character(
            hair_color='#FFB6C1',
            eye_color='#4169E1',
            accessories=accessories
        )
        
        assert isinstance(character, Image.Image)
        assert character.mode == 'RGBA'
    
    def test_image_transparency(self, generator):
        """Test that generated images have transparency."""
        face = generator.generate_base_face()
        
        pixels = list(face.getdata())
        has_transparent = any(p[3] < 255 for p in pixels)
        has_opaque = any(p[3] > 0 for p in pixels)
        
        assert has_opaque
        assert has_transparent or len(pixels) > 0
