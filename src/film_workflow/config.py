"""Configuration contracts; runtime loading is intentionally not implemented yet."""

from dataclasses import dataclass
from typing import Final

DEFAULT_BLENDER_EXECUTABLE: Final[str] = "blender"
DEFAULT_COMFYUI_URL: Final[str] = "http://127.0.0.1:8188"


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """Typed settings for a future local/headless workflow runner.

    Blender and ComfyUI are external processes. PostgreSQL is deliberately
    optional for the first experiment and is represented as a capability rather
    than an implicit connection.
    """

    blender_executable: str = DEFAULT_BLENDER_EXECUTABLE
    comfyui_url: str = DEFAULT_COMFYUI_URL
    postgres_enabled: bool = False
