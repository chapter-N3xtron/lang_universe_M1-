"""Deterministic prompt builder for image generation.

Reads a character sheet and a scene brief, then outputs a formatted prompt
ready for ComfyUI / Stable Diffusion / Fooocus.
"""
import json
from pathlib import Path


def load_character(path="character_sheet.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(character, scene_brief: str, tags: list[str] | None = None) -> str:
    app = character["appearance"]
    identity = character["identity"]
    wardrobe = character["wardrobe"]

    subject = (
        f"{identity.get('age_range','')} {identity.get('ethnicity','')} {identity.get('gender','')}, "
        f"{app['hair']['length']} {app['hair']['color']} {app['hair']['style']} hair, "
        f"{app['eyes']['color']} eyes, {app['skin']['tone']} skin, {identity.get('body_type','')} body"
    )

    features = ", ".join(app.get("distinguishing_features", []))
    style = character["prompt_prefix"]
    quality = character["prompt_suffix"]
    tag_str = ", ".join(tags or character.get("personality_tags", []))

    prompt = f"{style} {subject}, {features}, {scene_brief}, {tag_str}, {quality}"
    return " ".join(prompt.split())


def build_negative_prompt() -> str:
    return (
        "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
        "fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, "
        "signature, watermark, username, blurry, deformed"
    )


if __name__ == "__main__":
    import sys
    character = load_character()
    scene = sys.argv[1] if len(sys.argv) > 1 else "standing in a sunlit room"
    print(build_prompt(character, scene))
    print("NEGATIVE:", build_negative_prompt())
