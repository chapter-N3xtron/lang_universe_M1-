"""
Image Processor Module
Provides image processing utilities: resize, crop, filters, etc.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import numpy as np

from utils.config_loader import ConfigLoader


class ImageProcessor:
    """Process and transform anime character images."""
    
    def __init__(self, config: Optional[ConfigLoader] = None):
        """
        Initialize image processor.
        
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
    
    def resize(
        self,
        image: Union[Image.Image, str],
        width: Optional[int] = None,
        height: Optional[int] = None,
        maintain_aspect: bool = True,
        resample: int = Image.LANCZOS
    ) -> Image.Image:
        """
        Resize an image.
        
        Args:
            image: PIL Image or path to image
            width: Target width
            height: Target height
            maintain_aspect: Whether to maintain aspect ratio
            resample: Resampling filter
            
        Returns:
            Resized PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        orig_width, orig_height = image.size
        
        if width is None and height is None:
            raise ValueError("At least one of width or height must be specified")
        
        if maintain_aspect:
            if width is None:
                ratio = height / orig_height
                width = int(orig_width * ratio)
            elif height is None:
                ratio = width / orig_width
                height = int(orig_height * ratio)
            else:
                ratio = min(width / orig_width, height / orig_height)
                width = int(orig_width * ratio)
                height = int(orig_height * ratio)
        
        return image.resize((width, height), resample=resample)
    
    def resize_to_preset(
        self,
        image: Union[Image.Image, str],
        preset: str = 'medium'
    ) -> Image.Image:
        """
        Resize image to a preset size.
        
        Args:
            image: PIL Image or path
            preset: Size preset ('thumbnail', 'medium', 'large')
            
        Returns:
            Resized PIL Image
        """
        presets = self.config.get('processing.resize.sizes', [
            {'name': 'thumbnail', 'width': 128, 'height': 128},
            {'name': 'medium', 'width': 256, 'height': 256},
            {'name': 'large', 'width': 1024, 'height': 1024}
        ])
        
        preset_config = next((p for p in presets if p['name'] == preset), None)
        if not preset_config:
            raise ValueError(f"Unknown preset: {preset}")
        
        return self.resize(image, preset_config['width'], preset_config['height'])
    
    def crop(
        self,
        image: Union[Image.Image, str],
        left: int,
        top: int,
        right: int,
        bottom: int
    ) -> Image.Image:
        """
        Crop an image.
        
        Args:
            image: PIL Image or path
            left: Left coordinate
            top: Top coordinate
            right: Right coordinate
            bottom: Bottom coordinate
            
        Returns:
            Cropped PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        return image.crop((left, top, right, bottom))
    
    def crop_to_square(
        self,
        image: Union[Image.Image, str],
        size: Optional[int] = None
    ) -> Image.Image:
        """
        Crop image to square (center crop).
        
        Args:
            image: PIL Image or path
            size: Target size (optional)
            
        Returns:
            Square cropped PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        width, height = image.size
        min_dim = min(width, height)
        
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        
        cropped = image.crop((left, top, right, bottom))
        
        if size:
            cropped = self.resize(cropped, size, size)
        
        return cropped
    
    def apply_blur(
        self,
        image: Union[Image.Image, str],
        radius: float = 2.0
    ) -> Image.Image:
        """
        Apply Gaussian blur.
        
        Args:
            image: PIL Image or path
            radius: Blur radius
            
        Returns:
            Blurred PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        return image.filter(ImageFilter.GaussianBlur(radius=radius))
    
    def apply_sharpen(
        self,
        image: Union[Image.Image, str],
        factor: float = 1.5
    ) -> Image.Image:
        """
        Apply sharpening filter.
        
        Args:
            image: PIL Image or path
            factor: Sharpening factor (>1 sharpens, <1 blurs)
            
        Returns:
            Sharpened PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(factor)
    
    def apply_grayscale(
        self,
        image: Union[Image.Image, str]
    ) -> Image.Image:
        """
        Convert to grayscale.
        
        Args:
            image: PIL Image or path
            
        Returns:
            Grayscale PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        return ImageOps.grayscale(image).convert('RGBA')
    
    def apply_sepia(
        self,
        image: Union[Image.Image, str]
    ) -> Image.Image:
        """
        Apply sepia tone filter.
        
        Args:
            image: PIL Image or path
            
        Returns:
            Sepia-toned PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        arr = np.array(image)
        
        sepia_matrix = np.array([
            [0.393, 0.769, 0.189],
            [0.349, 0.686, 0.168],
            [0.272, 0.534, 0.131]
        ])
        
        sepia_arr = np.dot(arr[..., :3], sepia_matrix.T)
        sepia_arr = np.clip(sepia_arr, 0, 255).astype(np.uint8)
        
        result = Image.fromarray(sepia_arr, mode='RGB')
        return result.convert('RGBA')
    
    def adjust_brightness(
        self,
        image: Union[Image.Image, str],
        factor: float = 1.0
    ) -> Image.Image:
        """
        Adjust image brightness.
        
        Args:
            image: PIL Image or path
            factor: Brightness factor (>1 brighter, <1 darker)
            
        Returns:
            Adjusted PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(factor)
    
    def adjust_contrast(
        self,
        image: Union[Image.Image, str],
        factor: float = 1.0
    ) -> Image.Image:
        """
        Adjust image contrast.
        
        Args:
            image: PIL Image or path
            factor: Contrast factor (>1 more contrast, <1 less)
            
        Returns:
            Adjusted PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    
    def adjust_color(
        self,
        image: Union[Image.Image, str],
        factor: float = 1.0
    ) -> Image.Image:
        """
        Adjust color saturation.
        
        Args:
            image: PIL Image or path
            factor: Saturation factor (>1 more saturated, 0 grayscale)
            
        Returns:
            Adjusted PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        enhancer = ImageEnhance.Color(image)
        return enhancer.enhance(factor)
    
    def add_border(
        self,
        image: Union[Image.Image, str],
        border_width: int,
        color: str = '#FFFFFF'
    ) -> Image.Image:
        """
        Add a border to the image.
        
        Args:
            image: PIL Image or path
            border_width: Border width in pixels
            color: Border color (hex or RGB)
            
        Returns:
            PIL Image with border
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        return ImageOps.expand(image, border=border_width, fill=color)
    
    def add_padding(
        self,
        image: Union[Image.Image, str],
        padding: int,
        color: str = '#000000'
    ) -> Image.Image:
        """
        Add padding to the image.
        
        Args:
            image: PIL Image or path
            padding: Padding size in pixels
            color: Padding color
            
        Returns:
            PIL Image with padding
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        new_width = image.width + padding * 2
        new_height = image.height + padding * 2
        
        result = Image.new('RGBA', (new_width, new_height), color)
        result.paste(image, (padding, padding))
        
        return result
    
    def rotate(
        self,
        image: Union[Image.Image, str],
        angle: float,
        expand: bool = False
    ) -> Image.Image:
        """
        Rotate the image.
        
        Args:
            image: PIL Image or path
            angle: Rotation angle in degrees
            expand: Expand output to fit rotated image
            
        Returns:
            Rotated PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        return image.rotate(angle, expand=expand, resample=Image.BICUBIC)
    
    def flip(
        self,
        image: Union[Image.Image, str],
        horizontal: bool = True
    ) -> Image.Image:
        """
        Flip the image.
        
        Args:
            image: PIL Image or path
            horizontal: Flip horizontally (True) or vertically (False)
            
        Returns:
            Flipped PIL Image
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        if horizontal:
            return image.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            return image.transpose(Image.FLIP_TOP_BOTTOM)
    
    def apply_filter_chain(
        self,
        image: Union[Image.Image, str],
        filters: List[Dict]
    ) -> Image.Image:
        """
        Apply a chain of filters.
        
        Args:
            image: PIL Image or path
            filters: List of filter configurations
            
        Returns:
            Processed PIL Image
        """
        result = image if isinstance(image, Image.Image) else Image.open(image)
        
        for filter_config in filters:
            filter_name = filter_config.get('name')
            params = filter_config.get('params', {})
            
            if filter_name == 'blur':
                result = self.apply_blur(result, params.get('radius', 2))
            elif filter_name == 'sharpen':
                result = self.apply_sharpen(result, params.get('factor', 1.5))
            elif filter_name == 'grayscale':
                result = self.apply_grayscale(result)
            elif filter_name == 'sepia':
                result = self.apply_sepia(result)
            elif filter_name == 'brightness':
                result = self.adjust_brightness(result, params.get('factor', 1.0))
            elif filter_name == 'contrast':
                result = self.adjust_contrast(result, params.get('factor', 1.0))
            elif filter_name == 'color':
                result = self.adjust_color(result, params.get('factor', 1.0))
        
        return result
    
    def process_and_save(
        self,
        image: Union[Image.Image, str],
        filename: str,
        operations: Optional[List[Dict]] = None,
        format: str = 'png'
    ) -> Path:
        """
        Process and save an image.
        
        Args:
            image: PIL Image or path
            filename: Output filename
            operations: List of operations to apply
            format: Output format
            
        Returns:
            Path to saved file
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        if operations:
            image = self.apply_filter_chain(image, operations)
        
        output_dir = self.output_paths['processed']
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not filename.endswith(f'.{format}'):
            filename = f'{filename}.{format}'
        
        output_path = output_dir / filename
        image.save(output_path, format=format.upper())
        
        return output_path
    
    def create_thumbnail_set(
        self,
        image: Union[Image.Image, str],
        base_filename: str,
        format: str = 'png'
    ) -> Dict[str, Path]:
        """
        Create a set of thumbnails at different sizes.
        
        Args:
            image: PIL Image or path
            base_filename: Base filename for output
            format: Output format
            
        Returns:
            Dictionary mapping size names to file paths
        """
        if isinstance(image, str):
            image = Image.open(image)
        
        results = {}
        sizes = self.config.get('processing.resize.sizes', [
            {'name': 'thumbnail', 'width': 128, 'height': 128},
            {'name': 'medium', 'width': 256, 'height': 256},
            {'name': 'large', 'width': 1024, 'height': 1024}
        ])
        
        for size_config in sizes:
            resized = self.resize(image, size_config['width'], size_config['height'])
            filename = f"{base_filename}_{size_config['name']}"
            path = self.process_and_save(resized, filename, format=format)
            results[size_config['name']] = path
        
        return results
