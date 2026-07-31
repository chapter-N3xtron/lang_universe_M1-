#!/usr/bin/env python3
"""Export the canonical Jasper response schema for frontend code generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from src.visual_models import jasper_response_json_schema  # noqa: E402

OUTPUT = (
    REPO_ROOT
    / "agent-chat-ui"
    / "src"
    / "lib"
    / "visual"
    / "jasper-response.schema.json"
)
def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Ajv validates the generated oneOf branches directly. Pydantic's optional
    # OpenAPI discriminator mapping is not portable JSON Schema and is rejected
    # by Ajv, so it is deliberately omitted from the browser contract.
    schema = jasper_response_json_schema()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(OUTPUT.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
