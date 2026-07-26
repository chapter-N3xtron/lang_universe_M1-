"""
Test suite for BatchGenerator
"""

import pytest
from pathlib import Path
from PIL import Image
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.batch_generator import BatchGenerator
from utils.config_loader import ConfigLoader


class TestBatchGenerator:
    """Test cases for the batch generator."""
    
    @pytest.fixture
    def batch_generator(self, tmp_path):
        """Create a batch generator instance for testing."""
        config = ConfigLoader()
        bg = BatchGenerator(config, max_workers=2)
        bg.output_paths['base'] = tmp_path / 'images'
        bg.output_paths['base'].mkdir(parents=True, exist_ok=True)
        bg.output_paths['generated'] = tmp_path / 'images' / 'generated'
        bg.output_paths['processed'] = tmp_path / 'images' / 'processed'
        bg.output_paths['generated'].mkdir(parents=True, exist_ok=True)
        bg.output_paths['processed'].mkdir(parents=True, exist_ok=True)
        return bg
    
    def test_init(self, batch_generator):
        """Test batch generator initialization."""
        assert batch_generator is not None
        assert batch_generator.generator is not None
        assert batch_generator.processor is not None
        assert batch_generator.max_workers == 2
    
    def test_generate_expression_variants(self, batch_generator):
        """Test generating expression variants."""
        paths = batch_generator.generate_expression_variants(
            base_name='test_expr',
            hair_color='#FFB6C1',
            eye_color='#4169E1'
        )
        
        assert len(paths) > 0
        assert all(p.exists() for p in paths)
    
    def test_generate_hair_color_variants(self, batch_generator):
        """Test generating hair color variants."""
        hair_colors = ['#FFB6C1', '#87CEEB', '#DDA0DD']
        
        paths = batch_generator.generate_hair_color_variants(
            base_name='test_hair',
            hair_colors=hair_colors,
            eye_color='#4169E1'
        )
        
        assert len(paths) == len(hair_colors)
        assert all(p.exists() for p in paths)
    
    def test_generate_eye_color_variants(self, batch_generator):
        """Test generating eye color variants."""
        eye_colors = ['#4169E1', '#32CD32', '#FF69B4']
        
        paths = batch_generator.generate_eye_color_variants(
            base_name='test_eyes',
            eye_colors=eye_colors,
            hair_color='#FFB6C1'
        )
        
        assert len(paths) == len(eye_colors)
        assert all(p.exists() for p in paths)
    
    def test_generate_accessory_variants(self, batch_generator):
        """Test generating accessory variants."""
        accessories = [
            {'name': 'bow', 'colors': ['#FF1493']},
            {'name': 'glasses', 'colors': ['#000000']}
        ]
        
        paths = batch_generator.generate_accessory_variants(
            base_name='test_acc',
            accessory_configs=accessories
        )
        
        assert len(paths) == len(accessories)
        assert all(p.exists() for p in paths)
    
    def test_generate_full_combinations(self, batch_generator):
        """Test generating full combinations."""
        paths = batch_generator.generate_full_combinations(
            base_name='test_combo',
            hair_colors=['#FFB6C1', '#87CEEB'],
            eye_colors=['#4169E1', '#32CD32'],
            expressions=['happy', 'neutral'],
            hair_styles=['long'],
            accessory_options=[None]
        )
        
        expected_count = 2 * 2 * 2 * 1 * 1
        assert len(paths) == expected_count
        assert all(p.exists() for p in paths)
    
    def test_batch_resize(self, batch_generator, tmp_path):
        """Test batch resize operation."""
        input_dir = tmp_path / 'input'
        input_dir.mkdir()
        
        for i in range(3):
            img = Image.new('RGBA', (512, 512), (255, 0, 0, 255))
            img.save(input_dir / f'image_{i}.png')
        
        results = batch_generator.batch_resize(
            str(input_dir),
            output_subdir='resized_test'
        )
        
        assert len(results) == 3
        for filename, paths in results.items():
            assert len(paths) > 0
            assert all(p.exists() for p in paths)
    
    def test_batch_apply_filter(self, batch_generator, tmp_path):
        """Test batch filter application."""
        input_dir = tmp_path / 'input'
        input_dir.mkdir()
        
        for i in range(2):
            img = Image.new('RGBA', (512, 512), (255, 0, 0, 255))
            img.save(input_dir / f'image_{i}.png')
        
        filter_config = {'name': 'grayscale', 'params': {}}
        
        paths = batch_generator.batch_apply_filter(
            str(input_dir),
            filter_config=filter_config,
            output_subdir='filtered_test'
        )
        
        assert len(paths) == 2
        assert all(p.exists() for p in paths)
    
    def test_parallel_generate(self, batch_generator):
        """Test parallel generation."""
        configs = [
            {'name': 'char1', 'hair_color': '#FFB6C1', 'eye_color': '#4169E1'},
            {'name': 'char2', 'hair_color': '#87CEEB', 'eye_color': '#32CD32'},
            {'name': 'char3', 'hair_color': '#DDA0DD', 'eye_color': '#FF69B4'}
        ]
        
        paths = batch_generator.parallel_generate(configs, 'parallel_test')
        
        assert len(paths) == len(configs)
        assert all(p.exists() for p in paths)
    
    def test_save_generation_log(self, batch_generator):
        """Test saving generation log."""
        batch_generator.generate_and_save(
            'test_log',
            hair_color='#FFB6C1',
            eye_color='#4169E1'
        )
        
        log_path = batch_generator.save_generation_log()
        
        assert log_path.exists()
        assert log_path.suffix == '.json'
    
    def test_get_generation_stats(self, batch_generator):
        """Test getting generation statistics."""
        batch_generator.generate_and_save('test1', hair_color='#FFB6C1')
        batch_generator.generate_and_save('test2', hair_color='#87CEEB')
        
        stats = batch_generator.get_generation_stats()
        
        assert 'total_generated' in stats
        assert stats['total_generated'] >= 2
    
    def test_generation_log_metadata(self, batch_generator):
        """Test that generation log includes metadata."""
        batch_generator.generate_and_save(
            'test_meta',
            hair_color='#FFB6C1',
            expression='happy'
        )
        
        log = batch_generator._generation_log[-1]
        
        assert 'timestamp' in log
        assert 'name' in log
        assert 'path' in log
