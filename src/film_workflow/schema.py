"""Small, serializable domain placeholders for future workflow adapters."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class LensProfile:
    """Custom lens and film-look parameters to carry through a render job."""

    name: str
    focal_length_mm: float | None = None
    aperture: float | None = None
    film_look: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FilmProject:
    """Project-level intent; orchestration and persistence are future work."""

    project_id: str
    title: str
    lens_profile: LensProfile | None = None


@dataclass(frozen=True, slots=True)
class AssetRecord:
    """Asset metadata placeholder shared by Blender and ComfyUI stages."""

    asset_id: str
    kind: str
    uri: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JobProvenance:
    """Run provenance that may later be persisted in PostgreSQL."""

    job_id: str
    project_id: str
    created_at: datetime
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
