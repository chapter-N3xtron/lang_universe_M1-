"""
Batch Generator Module
Handles batch generation and processing of anime character images.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import json
from datetime import datetime
from tqdm import tqdm

from utils.config_loader import ConfigLoader
from scripts.anime_generator import AnimeCharacterGenerator
from scripts.image_processor import ImageProcessor


class BatchGenerator:
    """Generate and process batches of anime character images."""
    
    def __init__(self, config: Optional[ConfigLoader] = None, max_workers: int = 4):
        """
        Initialize batch generator.
        
        Args:
            config: Configuration loader instance
            max_workers: Maximum concurrent workers
        """
        self.config = config or ConfigLoader()
        self.max_workers = max_workers or self.config.get('batch.max_workers', 4)
        self.generator = AnimeCharacterGenerator(self.config)
        self.processor = ImageProcessor(self.config)
        self.output_paths = self.config.get_output_paths()
        self._generation_log: List[Dict] = []
    
    def generate_expression_variants(
        self,
        base_name: str,
        hair_color: Optional[str] = None,
        eye_color: Optional[str] = None,
        skin_tone: Optional[str] = None,
        hair_style: str = 'long',
        accessories: Optional[List[Dict]] = None
    ) -> List[Path]:
        """
        Generate character with all expression variants.
        
        Args:
            base_name: Base name for output files
            hair_color: Hair color
            eye_color: Eye color
            skin_tone: Skin tone
            hair_style: Hair style
            accessories: List of accessories
            
        Returns:
            List of generated file paths
        """
        expressions = self.config.get_expressions()
        results = []
        
        for expr in expressions:
            name = f"{base_name}_{expr['name']}"
            path = self.generator.generate_and_save(
                name,
                hair_color=hair_color,
                eye_color=eye_color,
                skin_tone=skin_tone,
                expression=expr['name'],
                hair_style=hair_style,
                accessories=accessories,
                include_blush=expr.get('blush', False)
            )
            results.append(path)
            self._log_generation(name, path, {'expression': expr['name']})
        
        return results
    
    def generate_hair_color_variants(
        self,
        base_name: str,
        hair_colors: Optional[List[str]] = None,
        eye_color: Optional[str] = None,
        skin_tone: Optional[str] = None,
        expression: str = 'neutral',
        hair_style: str = 'long'
    ) -> List[Path]:
        """
        Generate character with different hair colors.
        
        Args:
            base_name: Base name for output files
            hair_colors: List of hair colors
            eye_color: Eye color
            skin_tone: Skin tone
            expression: Expression
            hair_style: Hair style
            
        Returns:
            List of generated file paths
        """
        if hair_colors is None:
            hair_colors = self.config.get('character.default_hair_colors', [])
        
        results = []
        
        for color in hair_colors:
            name = f"{base_name}_hair_{color[1:]}"
            path = self.generator.generate_and_save(
                name,
                hair_color=color,
                eye_color=eye_color,
                skin_tone=skin_tone,
                expression=expression,
                hair_style=hair_style
            )
            results.append(path)
            self._log_generation(name, path, {'hair_color': color})
        
        return results
    
    def generate_eye_color_variants(
        self,
        base_name: str,
        eye_colors: Optional[List[str]] = None,
        hair_color: Optional[str] = None,
        skin_tone: Optional[str] = None,
        expression: str = 'neutral',
        hair_style: str = 'long'
    ) -> List[Path]:
        """
        Generate character with different eye colors.
        
        Args:
            base_name: Base name for output files
            eye_colors: List of eye colors
            hair_color: Hair color
            skin_tone: Skin tone
            expression: Expression
            hair_style: Hair style
            
        Returns:
            List of generated file paths
        """
        if eye_colors is None:
            eye_colors = self.config.get('character.default_eye_colors', [])
        
        results = []
        
        for color in eye_colors:
            name = f"{base_name}_eyes_{color[1:]}"
            path = self.generator.generate_and_save(
                name,
                hair_color=hair_color,
                eye_color=color,
                skin_tone=skin_tone,
                expression=expression,
                hair_style=hair_style
            )
            results.append(path)
            self._log_generation(name, path, {'eye_color': color})
        
        return results
    
    def generate_accessory_variants(
        self,
        base_name: str,
        accessory_configs: Optional[List[Dict]] = None,
        hair_color: Optional[str] = None,
        eye_color: Optional[str] = None,
        skin_tone: Optional[str] = None,
        expression: str = 'neutral'
    ) -> List[Path]:
        """
        Generate character with different accessories.
        
        Args:
            base_name: Base name for output files
            accessory_configs: List of accessory configurations
            hair_color: Hair color
            eye_color: Eye color
            skin_tone: Skin tone
            expression: Expression
            
        Returns:
            List of generated file paths
        """
        if accessory_configs is None:
            accessory_configs = self.config.get_accessories()
        
        results = []
        
        for acc_config in accessory_configs:
            name = f"{base_name}_{acc_config['name']}"
            accessories = [{
                'type': acc_config['name'],
                'color': acc_config['colors'][0] if acc_config.get('colors') else '#FF1493'
            }]
            
            path = self.generator.generate_and_save(
                name,
                hair_color=hair_color,
                eye_color=eye_color,
                skin_tone=skin_tone,
                expression=expression,
                accessories=accessories
            )
            results.append(path)
            self._log_generation(name, path, {'accessory': acc_config['name']})
        
        return results
    
    def generate_full_combinations(
        self,
        base_name: str,
        hair_colors: Optional[List[str]] = None,
        eye_colors: Optional[List[str]] = None,
        expressions: Optional[List[str]] = None,
        hair_styles: Optional[List[str]] = None,
        accessory_options: Optional[List[Dict]] = None
    ) -> List[Path]:
        """
        Generate all combinations of parameters.
        
        Args:
            base_name: Base name for output files
            hair_colors: List of hair colors
            eye_colors: List of eye colors
            expressions: List of expressions
            hair_styles: List of hair styles
            accessory_options: List of accessory options
            
        Returns:
            List of generated file paths
        """
        if hair_colors is None:
            hair_colors = self.config.get('character.default_hair_colors', [])[:3]
        if eye_colors is None:
            eye_colors = self.config.get('character.default_eye_colors', [])[:3]
        if expressions is None:
            expressions = ['neutral', 'happy', 'sad']
        if hair_styles is None:
            hair_styles = ['long', 'short']
        if accessory_options is None:
            accessory_options = [None, [{'type': 'bow', 'color': '#FF1493'}]]
        
        results = []
        total = len(hair_colors) * len(eye_colors) * len(expressions) * len(hair_styles) * len(accessory_options)
        
        with tqdm(total=total, desc='Generating combinations') as pbar:
            for hair in hair_colors:
                for eye in eye_colors:
                    for expr in expressions:
                        for style in hair_styles:
                            for accs in accessory_options:
                                name = f"{base_name}_{hair[1:]}_{eye[1:]}_{expr}_{style}"
                                if accs:
                                    name += f"_{accs[0]['type']}"
                                
                                path = self.generator.generate_and_save(
                                    name,
                                    hair_color=hair,
                                    eye_color=eye,
                                    skin_tone=None,
                                    expression=expr,
                                    hair_style=style,
                                    accessories=accs
                                )
                                results.append(path)
                                self._log_generation(name, path)
                                pbar.update(1)
        
        return results
    
    def batch_resize(
        self,
        input_dir: str,
        output_subdir: str = 'resized',
        sizes: Optional[List[Dict]] = None
    ) -> Dict[str, List[Path]]:
        """
        Batch resize all images in a directory.
        
        Args:
            input_dir: Input directory path
            output_subdir: Output subdirectory name
            sizes: List of size configurations
            
        Returns:
            Dictionary mapping input filenames to output paths
        """
        if sizes is None:
            sizes = self.config.get('processing.resize.sizes', [
                {'name': 'thumbnail', 'width': 128, 'height': 128},
                {'name': 'medium', 'width': 256, 'height': 256}
            ])
        
        input_path = Path(input_dir)
        output_base = self.output_paths['processed'] / output_subdir
        output_base.mkdir(parents=True, exist_ok=True)
        
        image_files = list(input_path.glob('*.png')) + list(input_path.glob('*.jpg'))
        results = {}
        
        with tqdm(total=len(image_files), desc='Batch resizing') as pbar:
            for img_path in image_files:
                results[img_path.name] = []
                
                with Image.open(img_path) as img:
                    for size_config in sizes:
                        resized = self.processor.resize(
                            img,
                            size_config['width'],
                            size_config['height']
                        )
                        output_name = f"{img_path.stem}_{size_config['name']}{img_path.suffix}"
                        output_path = output_base / output_name
                        resized.save(output_path)
                        results[img_path.name].append(output_path)
                
                pbar.update(1)
        
        return results
    
    def batch_apply_filter(
        self,
        input_dir: str,
        filter_config: Dict,
        output_subdir: str = 'filtered'
    ) -> List[Path]:
        """
        Batch apply a filter to all images in a directory.
        
        Args:
            input_dir: Input directory path
            filter_config: Filter configuration
            output_subdir: Output subdirectory name
            
        Returns:
            List of output file paths
        """
        input_path = Path(input_dir)
        output_base = self.output_paths['processed'] / output_subdir
        output_base.mkdir(parents=True, exist_ok=True)
        
        image_files = list(input_path.glob('*.png')) + list(input_path.glob('*.jpg'))
        results = []
        
        with tqdm(total=len(image_files), desc=f"Applying {filter_config['name']}") as pbar:
            for img_path in image_files:
                with Image.open(img_path) as img:
                    processed = self.processor.apply_filter_chain(img, [filter_config])
                    output_name = f"{img_path.stem}_{filter_config['name']}{img_path.suffix}"
                    output_path = output_base / output_name
                    processed.save(output_path)
                    results.append(output_path)
                
                pbar.update(1)
        
        return results
    
    def parallel_generate(
        self,
        character_configs: List[Dict],
        batch_name: str
    ) -> List[Path]:
        """
        Generate multiple characters in parallel.
        
        Args:
            character_configs: List of character configurations
            batch_name: Batch name for organization
            
        Returns:
            List of generated file paths
        """
        results = []
        output_dir = self.output_paths['generated'] / batch_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        def generate_single(config: Dict) -> Tuple[str, Path]:
            name = config.get('name', f"char_{len(results)}")
            path = self.generator.generate_and_save(
                f"{batch_name}/{name}",
                **{k: v for k, v in config.items() if k != 'name'}
            )
            return name, path
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(generate_single, cfg): cfg for cfg in character_configs}
            
            for future in tqdm(as_completed(futures), total=len(futures), desc='Parallel generation'):
                config = futures[future]
                try:
                    name, path = future.result()
                    results.append(path)
                    self._log_generation(name, path, config)
                except Exception as e:
                    print(f"Error generating {config.get('name', 'unknown')}: {e}")
        
        return results
    
    def _log_generation(self, name: str, path: Path, metadata: Optional[Dict] = None):
        """Log a generation event."""
        self._generation_log.append({
            'timestamp': datetime.now().isoformat(),
            'name': name,
            'path': str(path),
            'metadata': metadata or {}
        })
    
    def save_generation_log(self, log_path: Optional[str] = None) -> Path:
        """
        Save generation log to file.
        
        Args:
            log_path: Output log path
            
        Returns:
            Path to saved log file
        """
        if log_path is None:
            log_path = self.output_paths['generated'] / 'generation_log.json'
        else:
            log_path = Path(log_path)
        
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_path, 'w') as f:
            json.dump(self._generation_log, f, indent=2)
        
        return log_path
    
    def get_generation_stats(self) -> Dict:
        """
        Get statistics about generated images.
        
        Returns:
            Dictionary with generation statistics
        """
        return {
            'total_generated': len(self._generation_log),
            'by_expression': {},
            'by_hair_color': {},
            'by_eye_color': {}
        }
