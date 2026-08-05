from unittest.mock import MagicMock, patch

from langgraph.store.memory import InMemoryStore

from src import research_evidence


def _runtime(tmp_path, store=None):
    return MagicMock(
        tool_call_id="research-tool-1",
        store=store or InMemoryStore(),
        state={
            "workspace": str(tmp_path),
            "thread_identity": "thread-1",
            "user_identity": "local-owner-v1",
            "messages": [],
        },
    )


def test_visited_page_body_and_session_reference_are_saved_once(tmp_path):
    runtime = _runtime(tmp_path)
    with patch.object(
        research_evidence,
        "_read_url",
        MagicMock(invoke=MagicMock(return_value="Complete page text")),
    ):
        first = research_evidence.research_read_url.func(
            url="https://example.com/page", runtime=runtime
        )
        second = research_evidence.research_read_url.func(
            url="https://example.com/page", runtime=runtime
        )

    source_id = first.update["session_evidence"][0]["id"]
    assert second.update["session_evidence"][0]["id"] == source_id
    body = runtime.store.get(("local-owner-v1", "research-evidence"), source_id)
    assert body.value["content"] == "Complete page text"
    assert runtime.store.get(
        ("local-owner-v1", "session-sources", "thread-1"), source_id
    )


def test_search_results_are_saved_as_snippets_not_visited_pages(tmp_path):
    runtime = _runtime(tmp_path)
    with patch.object(
        research_evidence,
        "_web_search",
        MagicMock(
            invoke=MagicMock(
                return_value=(
                    "1. First source\n   URL: https://example.com/one\n   A snippet\n\n"
                    "2. Second source\n   URL: https://example.com/two\n   Another snippet"
                )
            )
        ),
    ):
        command = research_evidence.research_web_search.func(
            query="example", runtime=runtime
        )

    refs = command.update["session_evidence"]
    assert [ref["kind"] for ref in refs] == ["web_snippet", "web_snippet"]
    assert [ref["query"] for ref in refs] == ["example", "example"]


def test_workspace_source_is_read_only_and_blocks_sensitive_paths(tmp_path):
    (tmp_path / "notes.md").write_text("safe notes")
    (tmp_path / ".env").write_text("SECRET=not-returned")
    runtime = _runtime(tmp_path)

    allowed = research_evidence.read_workspace_source.func(
        file_path="notes.md", runtime=runtime
    )
    denied = research_evidence.read_workspace_source.func(
        file_path=".env", runtime=runtime
    )

    assert "safe notes" in allowed.update["messages"][0].content
    assert "unsupported" in denied.update["messages"][0].content
    assert "SECRET" not in denied.update["messages"][0].content


def test_uploaded_text_keeps_segment_and_truncation_metadata(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.state["messages"] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text-plain",
                    "title": "brief.pdf",
                    "text": "extracted text",
                    "metadata": {
                        "filename": "brief.pdf",
                        "segments": [{"page": 1}],
                        "truncated": True,
                    },
                }
            ],
        }
    ]

    command = research_evidence.ingest_uploaded_sources.func(runtime=runtime)
    ref = command.update["session_evidence"][0]
    assert ref["kind"] == "upload"
    assert ref["segments"] == [{"page": 1}]
    assert ref["truncated"] is True


def test_saved_source_reopens_without_network(tmp_path):
    runtime = _runtime(tmp_path)
    ref = research_evidence.save_evidence(
        runtime,
        kind="web_url",
        locator="https://example.com",
        title="Example",
        content="saved body",
    )

    result = research_evidence.read_saved_source.func(
        source_id=ref["id"], runtime=runtime
    )
    assert "saved body" in result
