"""
Configuration Loader Module
Handles loading and validating configuration from YAML/JSON files.
"""

import yaml
import json
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigLoader:
    """Load and manage framework configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_path: Path to configuration file (YAML or JSON)
        """
        self.config_path = config_path or Path(__file__).parent.parent / 'config' / 'config.yaml'
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Configuration dictionary
        """
        path = Path(self.config_path)
        
        if not path.exists():
            self._config = self._get_default_config()
            return self._config
        
        content = path.read_text()
        
        if path.suffix in ['.yaml', '.yml']:
            self._config = yaml.safe_load(content)
        elif path.suffix == '.json':
            self._config = json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")
        
        return self._config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            'image': {
                'default_width': 512,
                'default_height': 512,
                'formats': ['png', 'jpg'],
                'quality': 95
            },
            'character': {
                'default_hair_colors': ['#FFB6C1'],
                'default_eye_colors': ['#4169E1'],
                'default_skin_tones': ['#FFE4C4']
            },
            'expressions': [
                {'name': 'neutral', 'mouth_curve': 0.0, 'eye_openness': 0.7, 'blush': False}
            ],
            'output': {
                'base_dir': 'images',
                'generated_subdir': 'generated',
                'processed_subdir': 'processed'
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., 'image.default_width')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_image_settings(self) -> Dict[str, Any]:
        """Get image-related settings."""
        return self._config.get('image', {})
    
    def get_character_settings(self) -> Dict[str, Any]:
        """Get character-related settings."""
        return self._config.get('character', {})
    
    def get_expressions(self) -> list:
        """Get expression definitions."""
        return self._config.get('expressions', [])
    
    def get_accessories(self) -> list:
        """Get accessory definitions."""
        return self._config.get('accessories', [])
    
    def get_output_paths(self) -> Dict[str, Path]:
        """Get output directory paths."""
        base = Path(self._config.get('output', {}).get('base_dir', 'images'))
        return {
            'base': base,
            'generated': base / self._config.get('output', {}).get('generated_subdir', 'generated'),
            'processed': base / self._config.get('output', {}).get('processed_subdir', 'processed'),
            'templates': base / self._config.get('output', {}).get('templates_subdir', 'templates')
        }
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get full configuration dictionary."""
        return self._config
