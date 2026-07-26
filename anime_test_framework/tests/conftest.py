"""
Pytest configuration and fixtures for anime test framework.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope='session')
def test_config():
    """Create a test configuration."""
    from utils.config_loader import ConfigLoader
    
    config = ConfigLoader()
    return config


@pytest.fixture(scope='session')
def test_output_dir(tmp_path_factory):
    """Create a temporary output directory for tests."""
    return tmp_path_factory.mktemp('test_images')


@pytest.fixture
def sample_character_data():
    """Sample character configuration for tests."""
    return {
        'hair_color': '#FFB6C1',
        'eye_color': '#4169E1',
        'skin_tone': '#FFE4C4',
        'expression': 'happy',
        'hair_style': 'long'
    }


@pytest.fixture
def sample_accessories():
    """Sample accessories configuration for tests."""
    return [
        {'type': 'bow', 'color': '#FF1493'},
        {'type': 'glasses', 'color': '#000000'}
    ]


@pytest.fixture
def expression_list():
    """List of all expressions for testing."""
    return ['happy', 'sad', 'surprised', 'angry', 'neutral']


@pytest.fixture
def hair_style_list():
    """List of all hair styles for testing."""
    return ['long', 'short', 'twin_tails', 'bob']


@pytest.fixture
def color_test_cases():
    """Test cases for color utilities."""
    return [
        ('#FF5733', (255, 87, 51)),
        ('#000000', (0, 0, 0)),
        ('#FFFFFF', (255, 255, 255)),
        ('#AABBCC', (170, 187, 204)),
    ]
