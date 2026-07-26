"""
Test suite for ImageProcessor
"""

import pytest
from pathlib import Path
from PIL import Image
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.image_processor import ImageProcessor
from utils.config_loader import ConfigLoader


class TestImageProcessor:
    """Test cases for the image processor."""
    
    @pytest.fixture
    def processor(self):
        """Create a processor instance for testing."""
        config = ConfigLoader()
        return ImageProcessor(config)
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample image for testing."""
        return Image.new('RGBA', (512, 512), (255, 0, 0, 255))
    
    def test_init(self, processor):
        """Test processor initialization."""
        assert processor is not None
        assert processor.config is not None
    
    def test_resize_width(self, processor, sample_image):
        """Test resize by width."""
        resized = processor.resize(sample_image, width=256)
        
        assert resized.size == (256, 256)
        assert resized.mode == 'RGBA'
    
    def test_resize_height(self, processor, sample_image):
        """Test resize by height."""
        resized = processor.resize(sample_image, height=256)
        
        assert resized.size == (256, 256)
    
    def test_resize_both(self, processor, sample_image):
        """Test resize by both dimensions."""
        resized = processor.resize(sample_image, width=256, height=128)
        
        assert resized.size == (256, 128)
    
    def test_resize_maintain_aspect(self, processor, sample_image):
        """Test resize with aspect ratio maintenance."""
        original_ratio = sample_image.width / sample_image.height
        resized = processor.resize(sample_image, width=256, maintain_aspect=True)
        
        new_ratio = resized.width / resized.height
        assert abs(original_ratio - new_ratio) < 0.01
    
    def test_resize_preset(self, processor, sample_image):
        """Test resize to preset size."""
        resized = processor.resize_to_preset(sample_image, 'thumbnail')
        
        assert resized.size == (128, 128)
    
    def test_resize_preset_medium(self, processor, sample_image):
        """Test resize to medium preset."""
        resized = processor.resize_to_preset(sample_image, 'medium')
        
        assert resized.size == (256, 256)
    
    def test_crop(self, processor, sample_image):
        """Test crop operation."""
        cropped = processor.crop(sample_image, 100, 100, 400, 400)
        
        assert cropped.size == (300, 300)
    
    def test_crop_to_square(self, processor):
        """Test crop to square."""
        rect_image = Image.new('RGBA', (600, 400), (0, 255, 0, 255))
        squared = processor.crop_to_square(rect_image)
        
        assert squared.size[0] == squared.size[1]
    
    def test_apply_blur(self, processor, sample_image):
        """Test blur filter."""
        blurred = processor.apply_blur(sample_image, radius=2)
        
        assert blurred.size == sample_image.size
        assert blurred.mode == 'RGBA'
    
    def test_apply_sharpen(self, processor, sample_image):
        """Test sharpen filter."""
        sharpened = processor.apply_sharpen(sample_image, factor=2.0)
        
        assert sharpened.size == sample_image.size
    
    def test_apply_grayscale(self, processor, sample_image):
        """Test grayscale conversion."""
        grayscale = processor.apply_grayscale(sample_image)
        
        assert grayscale.mode == 'RGBA'
    
    def test_apply_sepia(self, processor, sample_image):
        """Test sepia filter."""
        sepia = processor.apply_sepia(sample_image)
        
        assert sepia.size == sample_image.size
    
    def test_adjust_brightness_increase(self, processor, sample_image):
        """Test increase brightness."""
        brighter = processor.adjust_brightness(sample_image, factor=1.5)
        
        assert brighter.size == sample_image.size
    
    def test_adjust_brightness_decrease(self, processor, sample_image):
        """Test decrease brightness."""
        darker = processor.adjust_brightness(sample_image, factor=0.5)
        
        assert darker.size == sample_image.size
    
    def test_adjust_contrast(self, processor, sample_image):
        """Test contrast adjustment."""
        contrasted = processor.adjust_contrast(sample_image, factor=1.5)
        
        assert contrasted.size == sample_image.size
    
    def test_adjust_color(self, processor, sample_image):
        """Test color saturation adjustment."""
        saturated = processor.adjust_color(sample_image, factor=1.5)
        
        assert saturated.size == sample_image.size
    
    def test_add_border(self, processor, sample_image):
        """Test adding border."""
        bordered = processor.add_border(sample_image, border_width=10, color='#FFFFFF')
        
        assert bordered.size == (532, 532)
    
    def test_add_padding(self, processor, sample_image):
        """Test adding padding."""
        padded = processor.add_padding(sample_image, padding=20, color='#000000')
        
        assert padded.size == (552, 552)
    
    def test_rotate(self, processor, sample_image):
        """Test rotation."""
        rotated = processor.rotate(sample_image, angle=45)
        
        assert rotated.size == sample_image.size
    
    def test_rotate_expand(self, processor, sample_image):
        """Test rotation with expand."""
        rotated = processor.rotate(sample_image, angle=45, expand=True)
        
        assert rotated.size[0] > sample_image.size[0]
        assert rotated.size[1] > sample_image.size[1]
    
    def test_flip_horizontal(self, processor, sample_image):
        """Test horizontal flip."""
        flipped = processor.flip(sample_image, horizontal=True)
        
        assert flipped.size == sample_image.size
    
    def test_flip_vertical(self, processor, sample_image):
        """Test vertical flip."""
        flipped = processor.flip(sample_image, horizontal=False)
        
        assert flipped.size == sample_image.size
    
    def test_filter_chain(self, processor, sample_image):
        """Test applying multiple filters."""
        filters = [
            {'name': 'blur', 'params': {'radius': 2}},
            {'name': 'sharpen', 'params': {'factor': 1.5}}
        ]
        
        result = processor.apply_filter_chain(sample_image, filters)
        
        assert result.size == sample_image.size
    
    def test_process_and_save(self, processor, sample_image, tmp_path):
        """Test processing and saving image."""
        processor.output_paths['processed'] = tmp_path
        
        operations = [{'name': 'blur', 'params': {'radius': 2}}]
        saved_path = processor.process_and_save(
            sample_image,
            'test_processed',
            operations=operations,
            format='png'
        )
        
        assert saved_path.exists()
        assert saved_path.suffix == '.png'
    
    def test_create_thumbnail_set(self, processor, sample_image, tmp_path):
        """Test creating thumbnail set."""
        processor.output_paths['processed'] = tmp_path
        
        thumbnails = processor.create_thumbnail_set(sample_image, 'test_thumb')
        
        assert 'thumbnail' in thumbnails
        assert 'medium' in thumbnails
        assert 'large' in thumbnails
        
        for name, path in thumbnails.items():
            assert path.exists()
