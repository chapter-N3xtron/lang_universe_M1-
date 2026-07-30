"""Read-only Deep Agents SDK integration probe.

Run this with the Python interpreter from the isolated ``deepagents-code``
uv tool environment. The probe deliberately exposes only filesystem read
operations and prints aggregate stream evidence rather than model output.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_ollama import ChatOllama


def _event_name(event: Any) -> str:
    if isinstance(event, tuple) and event:
        return str(event[0])
    if isinstance(event, dict):
        return str(event.get("type") or event.get("event") or "dict")
    return type(event).__name__


async def run_probe(workspace: Path, model_name: str, timeout: int) -> dict[str, Any]:
    model = ChatOllama(
        model=model_name,
        base_url="http://127.0.0.1:11434",
        temperature=0,
        num_ctx=8192,
        num_predict=256,
        validate_model_on_init=True,
    )
    agent = create_deep_agent(
        model=model,
        name="coding_agent_spike",
        system_prompt=(
            "You are running a read-only integration check. Never write, edit, "
            "delete, or execute files. Use read_file once on /README.md, then "
            "reply with the exact token DIRECT_OK and the Markdown title only."
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        permissions=[
            FilesystemPermission(operations=["read"], paths=["/**"], mode="allow"),
            FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
        ],
        checkpointer=False,
    )

    counts: Counter[str] = Counter()
    message_chunks = 0
    tool_events = 0
    final_messages = 0

    async def collect() -> None:
        nonlocal message_chunks, tool_events, final_messages
        async for event in agent.astream(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Read /README.md and report its title as instructed.",
                    }
                ]
            },
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            name = _event_name(event)
            counts[name] += 1
            rendered = repr(event)
            if "MessageChunk" in rendered:
                message_chunks += 1
            if "tool_call" in rendered or "read_file" in rendered:
                tool_events += 1
            if "DIRECT_OK" in rendered:
                final_messages += 1

    await asyncio.wait_for(collect(), timeout=timeout)
    return {
        "path": "direct-sdk",
        "model": model_name,
        "workspace_confined": True,
        "write_permission": "denied",
        "stream_event_counts": dict(sorted(counts.items())),
        "message_chunks": message_chunks,
        "tool_events": tool_events,
        "direct_ok_events": final_messages,
        "success": final_messages > 0 and tool_events > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model", default="qwen3.5:27b")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not (workspace / "README.md").is_file():
        raise SystemExit("workspace must contain README.md")

    result = asyncio.run(run_probe(workspace, args.model, args.timeout))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
