"""
Image Validator Module
Validates generated images against expected criteria.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
import numpy as np


class ImageValidator:
    """Validate generated anime character images."""
    
    def __init__(self):
        """Initialize the image validator."""
        self.validation_results: List[Dict] = []
    
    def validate_file_exists(self, path: str) -> bool:
        """
        Check if image file exists.
        
        Args:
            path: Path to image file
            
        Returns:
            True if file exists
        """
        return Path(path).exists()
    
    def validate_format(self, path: str, expected_formats: List[str]) -> Tuple[bool, str]:
        """
        Validate image format.
        
        Args:
            path: Path to image file
            expected_formats: List of acceptable formats
            
        Returns:
            Tuple of (is_valid, actual_format)
        """
        try:
            with Image.open(path) as img:
                actual_format = img.format.lower() if img.format else 'unknown'
                is_valid = actual_format in [f.lower() for f in expected_formats]
                return is_valid, actual_format
        except Exception as e:
            return False, f"error: {str(e)}"
    
    def validate_dimensions(
        self, 
        path: str, 
        expected_width: Optional[int] = None,
        expected_height: Optional[int] = None,
        tolerance: int = 0
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Validate image dimensions.
        
        Args:
            path: Path to image file
            expected_width: Expected width in pixels
            expected_height: Expected height in pixels
            tolerance: Acceptable deviation in pixels
            
        Returns:
            Tuple of (is_valid, actual_dimensions)
        """
        try:
            with Image.open(path) as img:
                width, height = img.size
                dims = {'width': width, 'height': height}
                
                valid = True
                if expected_width is not None:
                    valid &= abs(width - expected_width) <= tolerance
                if expected_height is not None:
                    valid &= abs(height - expected_height) <= tolerance
                
                return valid, dims
        except Exception as e:
            return False, {'error': str(e)}
    
    def validate_color_mode(self, path: str, expected_mode: str = 'RGB') -> Tuple[bool, str]:
        """
        Validate image color mode.
        
        Args:
            path: Path to image file
            expected_mode: Expected color mode (RGB, RGBA, L, etc.)
            
        Returns:
            Tuple of (is_valid, actual_mode)
        """
        try:
            with Image.open(path) as img:
                actual_mode = img.mode
                is_valid = actual_mode == expected_mode
                return is_valid, actual_mode
        except Exception as e:
            return False, f"error: {str(e)}"
    
    def validate_file_size(
        self, 
        path: str, 
        min_size: int = 0, 
        max_size: Optional[int] = None
    ) -> Tuple[bool, int]:
        """
        Validate file size.
        
        Args:
            path: Path to image file
            min_size: Minimum file size in bytes
            max_size: Maximum file size in bytes
            
        Returns:
            Tuple of (is_valid, actual_size)
        """
        size = Path(path).stat().st_size
        is_valid = size >= min_size and (max_size is None or size <= max_size)
        return is_valid, size
    
    def validate_not_corrupt(self, path: str) -> Tuple[bool, str]:
        """
        Validate image is not corrupt and can be fully loaded.
        
        Args:
            path: Path to image file
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            with Image.open(path) as img:
                img.verify()
            return True, "Image is valid"
        except Exception as e:
            return False, f"Corrupt: {str(e)}"
    
    def validate_brightness(
        self, 
        path: str, 
        min_brightness: float = 0.0,
        max_brightness: float = 255.0
    ) -> Tuple[bool, float]:
        """
        Validate image brightness level.
        
        Args:
            path: Path to image file
            min_brightness: Minimum average brightness (0-255)
            max_brightness: Maximum average brightness (0-255)
            
        Returns:
            Tuple of (is_valid, average_brightness)
        """
        try:
            with Image.open(path) as img:
                if img.mode != 'L':
                    img = img.convert('L')
                arr = np.array(img)
                brightness = float(np.mean(arr))
                is_valid = min_brightness <= brightness <= max_brightness
                return is_valid, brightness
        except Exception as e:
            return False, 0.0
    
    def run_full_validation(
        self, 
        path: str,
        expected_format: Optional[str] = None,
        expected_width: Optional[int] = None,
        expected_height: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Run complete validation suite on an image.
        
        Args:
            path: Path to image file
            expected_format: Expected file format
            expected_width: Expected width
            expected_height: Expected height
            
        Returns:
            Dictionary with all validation results
        """
        results = {
            'path': path,
            'exists': self.validate_file_exists(path),
            'format_valid': (False, 'unknown'),
            'dimensions_valid': (False, {}),
            'color_mode_valid': (False, 'unknown'),
            'not_corrupt': (False, 'unknown'),
            'file_size_valid': (False, 0),
            'brightness_valid': (False, 0.0)
        }
        
        if not results['exists']:
            results['error'] = 'File does not exist'
            return results
        
        if expected_format:
            results['format_valid'] = self.validate_format(path, [expected_format])
        
        results['dimensions_valid'] = self.validate_dimensions(
            path, expected_width, expected_height
        )
        
        results['color_mode_valid'] = self.validate_color_mode(path)
        results['not_corrupt'] = self.validate_not_corrupt(path)
        results['file_size_valid'] = self.validate_file_size(path, min_size=100)
        results['brightness_valid'] = self.validate_brightness(path)
        
        results['all_passed'] = all([
            results['exists'],
            results['format_valid'][0],
            results['dimensions_valid'][0],
            results['color_mode_valid'][0],
            results['not_corrupt'][0],
            results['file_size_valid'][0]
        ])
        
        self.validation_results.append(results)
        return results
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary of validation results.
        
        Returns:
            Dictionary with pass/fail counts
        """
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r.get('all_passed', False))
        return {
            'total': total,
            'passed': passed,
            'failed': total - passed
        }
