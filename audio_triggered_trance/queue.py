#!/usr/bin/env python3
"""Queue the workflow_api.json to a local ComfyUI server.

Patches the positive/negative prompt nodes from the character framework,
queues the job, and prints the ComfyUI prompt_id.
"""
import json
import sys
import uuid
from pathlib import Path

import requests


def load_workflow(path="workflow_api.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def patch_text_node(workflow: dict, node_id: str, text: str) -> dict:
    if node_id in workflow and "inputs" in workflow[node_id]:
        workflow[node_id]["inputs"]["text"] = text
    return workflow


def queue_workflow(workflow: dict, server="http://127.0.0.1:8188") -> dict:
    payload = {"prompt": workflow, "client_id": str(uuid.uuid4())}
    resp = requests.post(f"{server}/prompt", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


_TOOL_DISPATCH = {
    "bash": _tool_bash,
    "read": _tool_read,
    "glob": _tool_glob,
    "grep": _tool_grep,
    "edit": _tool_edit,
    "write": _tool_write,
    "build_image_framework": _tool_build_image_framework,
    "build_comfyui_workflow": _tool_build_comfyui_workflow,
    "register_character": _tool_register_character,
    "update_physical_description": _tool_update_physical_description,
    "place_image_order": _tool_place_image_order,
}


if __name__ == "__main__":
    wf = load_workflow()
    if len(sys.argv) > 2:
        wf = patch_text_node(wf, sys.argv[1], sys.argv[2])
    if len(sys.argv) > 4:
        wf = patch_text_node(wf, sys.argv[3], sys.argv[4])
    print(queue_workflow(wf))
