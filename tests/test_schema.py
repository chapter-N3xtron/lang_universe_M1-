from datetime import UTC, datetime

from film_workflow import FilmProject, JobProvenance, LensProfile, WorkflowConfig


def test_initial_contracts_are_constructible() -> None:
    lens = LensProfile(name="soft anamorphic", focal_length_mm=50, film_look="custom")
    project = FilmProject(project_id="demo", title="First test", lens_profile=lens)
    provenance = JobProvenance(
        job_id="job-1",
        project_id=project.project_id,
        created_at=datetime.now(UTC),
    )

    assert WorkflowConfig().postgres_enabled is False
    assert project.lens_profile == lens
    assert provenance.project_id == "demo"
