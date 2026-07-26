"""
Test suite for ImageValidator
"""

import pytest
from pathlib import Path
from PIL import Image
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.image_validator import ImageValidator


class TestImageValidator:
    """Test cases for the image validator."""
    
    @pytest.fixture
    def validator(self):
        """Create a validator instance for testing."""
        return ImageValidator()
    
    @pytest.fixture
    def sample_image_path(self, tmp_path):
        """Create a sample image file for testing."""
        img = Image.new('RGB', (512, 512), (255, 0, 0))
        img_path = tmp_path / 'test_image.png'
        img.save(img_path)
        return str(img_path)
    
    def test_init(self, validator):
        """Test validator initialization."""
        assert validator is not None
        assert validator.validation_results == []
    
    def test_validate_file_exists(self, validator, sample_image_path):
        """Test file existence validation."""
        assert validator.validate_file_exists(sample_image_path) is True
        assert validator.validate_file_exists('/nonexistent/path.png') is False
    
    def test_validate_format(self, validator, sample_image_path):
        """Test format validation."""
        is_valid, actual_format = validator.validate_format(
            sample_image_path,
            ['png', 'jpg']
        )
        
        assert is_valid is True
        assert actual_format == 'png'
    
    def test_validate_format_invalid(self, validator, sample_image_path):
        """Test format validation with invalid format."""
        is_valid, actual_format = validator.validate_format(
            sample_image_path,
            ['jpg', 'gif']
        )
        
        assert is_valid is False
        assert actual_format == 'png'
    
    def test_validate_dimensions(self, validator, sample_image_path):
        """Test dimension validation."""
        is_valid, dims = validator.validate_dimensions(
            sample_image_path,
            expected_width=512,
            expected_height=512
        )
        
        assert is_valid is True
        assert dims['width'] == 512
        assert dims['height'] == 512
    
    def test_validate_dimensions_wrong_size(self, validator, sample_image_path):
        """Test dimension validation with wrong size."""
        is_valid, dims = validator.validate_dimensions(
            sample_image_path,
            expected_width=256,
            expected_height=256
        )
        
        assert is_valid is False
        assert dims['width'] == 512
    
    def test_validate_dimensions_with_tolerance(self, validator, sample_image_path):
        """Test dimension validation with tolerance."""
        is_valid, dims = validator.validate_dimensions(
            sample_image_path,
            expected_width=510,
            tolerance=5
        )
        
        assert is_valid is True
    
    def test_validate_color_mode(self, validator, sample_image_path):
        """Test color mode validation."""
        is_valid, mode = validator.validate_color_mode(sample_image_path, 'RGB')
        
        assert is_valid is True
        assert mode == 'RGB'
    
    def test_validate_color_mode_mismatch(self, validator, sample_image_path):
        """Test color mode validation with mismatch."""
        is_valid, mode = validator.validate_color_mode(sample_image_path, 'RGBA')
        
        assert is_valid is False
        assert mode == 'RGB'
    
    def test_validate_file_size(self, validator, sample_image_path):
        """Test file size validation."""
        is_valid, size = validator.validate_file_size(
            sample_image_path,
            min_size=100,
            max_size=1000000
        )
        
        assert is_valid is True
        assert size > 0
    
    def test_validate_file_size_too_small(self, validator, sample_image_path):
        """Test file size validation with too small minimum."""
        is_valid, size = validator.validate_file_size(
            sample_image_path,
            min_size=10000000
        )
        
        assert is_valid is False
    
    def test_validate_not_corrupt(self, validator, sample_image_path):
        """Test corruption validation."""
        is_valid, message = validator.validate_not_corrupt(sample_image_path)
        
        assert is_valid is True
    
    def test_validate_not_corrupt_nonexistent(self, validator):
        """Test corruption validation on nonexistent file."""
        is_valid, message = validator.validate_not_corrupt('/nonexistent/file.png')
        
        assert is_valid is False
    
    def test_validate_brightness(self, validator, sample_image_path):
        """Test brightness validation."""
        is_valid, brightness = validator.validate_brightness(
            sample_image_path,
            min_brightness=0,
            max_brightness=255
        )
        
        assert is_valid is True
        assert 0 <= brightness <= 255
    
    def test_run_full_validation(self, validator, sample_image_path):
        """Test full validation suite."""
        results = validator.run_full_validation(
            sample_image_path,
            expected_format='png',
            expected_width=512,
            expected_height=512
        )
        
        assert results['exists'] is True
        assert results['format_valid'][0] is True
        assert results['dimensions_valid'][0] is True
        assert results['not_corrupt'][0] is True
        assert results['all_passed'] is True
    
    def test_run_full_validation_nonexistent(self, validator):
        """Test full validation on nonexistent file."""
        results = validator.run_full_validation('/nonexistent/file.png')
        
        assert results['exists'] is False
        assert results['all_passed'] is False
    
    def test_get_summary(self, validator, sample_image_path):
        """Test validation summary."""
        validator.run_full_validation(sample_image_path)
        validator.run_full_validation('/nonexistent/file.png')
        
        summary = validator.get_summary()
        
        assert summary['total'] == 2
        assert summary['passed'] == 1
        assert summary['failed'] == 1
    
    def test_validation_results_accumulation(self, validator, sample_image_path):
        """Test that validation results accumulate."""
        validator.run_full_validation(sample_image_path)
        validator.run_full_validation(sample_image_path)
        
        assert len(validator.validation_results) == 2
