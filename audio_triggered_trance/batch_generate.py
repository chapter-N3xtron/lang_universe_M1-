#!/usr/bin/env python3
"""Batch prompt generator: read scenes.txt, write prompts.jsonl."""
import json
from pathlib import Path
from prompt_engine import build_prompt, load_character


def main():
    character = load_character()
    scenes = Path("scenes.txt").read_text(encoding="utf-8").splitlines()
    out = []
    for i, scene in enumerate(scenes, 1):
        scene = scene.strip()
        if not scene:
            continue
        out.append({
            "id": f"img_{i:03d}",
            "scene": scene,
            "prompt": build_prompt(character, scene),
            "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, deformed",
        })
    Path("prompts.jsonl").write_text("\n".join(json.dumps(o) for o in out), encoding="utf-8")
    print(f"Wrote {len(out)} prompts to prompts.jsonl")


if __name__ == "__main__":
    main()
