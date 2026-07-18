#!/usr/bin/env python3
"""Patch the ComfyUI workflow and queue it.

Usage:
    python patch_and_queue.py "positive prompt" ["negative prompt"]

Reads workflow_api.json, optionally overwrites the positive (node 7)
and negative (node 8) prompts, then queues the job to ComfyUI.
"""
import json
import sys
from pathlib import Path

import requests


def patch_text_node(workflow: dict, node_id: str, text: str) -> dict:
    if node_id in workflow and "inputs" in workflow[node_id]:
        workflow[node_id]["inputs"]["text"] = text
    return workflow


def queue_workflow(workflow: dict, server="http://127.0.0.1:8188") -> dict:
    payload = {"prompt": workflow, "client_id": "anima-character"}
    resp = requests.post(f"{server}/prompt", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main():
    workflow_path = Path(__file__).with_name("workflow_api.json")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    if len(sys.argv) > 1:
        workflow = patch_text_node(workflow, "7", sys.argv[1])
    if len(sys.argv) > 2:
        workflow = patch_text_node(workflow, "8", sys.argv[2])

    print(queue_workflow(workflow))


if __name__ == "__main__":
    main()
