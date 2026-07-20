#!/usr/bin/env python3
"""Build a prompt and patch it into the ComfyUI workflow in one step.

Usage:
    python patch_and_queue.py "scene description"

This reads ../image_framework/character_sheet.json and scenes.txt,
builds the prompt with prompt_engine.py, then queues the workflow.
"""
import json
import sys
from pathlib import Path

import requests


def main():
    image_dir = Path("../image_framework")
    if not image_dir.exists():
        image_dir = Path("image_framework")

    sys.path.insert(0, str(image_dir))
    from prompt_engine import build_prompt, build_negative_prompt, load_character

    character = load_character(str(image_dir / "character_sheet.json"))
    scene = sys.argv[1] if len(sys.argv) > 1 else "standing in a sunlit room"
    positive = build_prompt(character, scene)
    negative = build_negative_prompt()

    workflow_path = Path("workflow_api.json")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    workflow["7"]["inputs"]["text"] = positive
    workflow["8"]["inputs"]["text"] = negative

    resp = requests.post(
        "http://127.0.0.1:8188/prompt",
        json={"prompt": workflow, "client_id": "anima-character"},
        timeout=60,
    )
    resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()
