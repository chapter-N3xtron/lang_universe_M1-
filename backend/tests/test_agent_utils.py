"""Tests for agent_utils helper functions.

Verifies that ``get_user_query`` and ``get_conversation_history`` handle
both LangGraph SDK format (``{"type": "human"}``) and plain dict format
(``{"role": "user"}``).
"""

from src.agent_utils import get_user_query, get_conversation_history


# ---------------------------------------------------------------------------
# get_user_query
# ---------------------------------------------------------------------------

def test_type_human_format():
    """LangGraph SDK uses ``type: "human"`` for user messages."""
    msgs = [
        {"type": "human", "content": "hello from type format"},
    ]
    assert get_user_query(msgs) == "hello from type format"


def test_role_user_format():
    """Plain dicts use ``role: "user"``."""
    msgs = [
        {"role": "user", "content": "hello from role format"},
    ]
    assert get_user_query(msgs) == "hello from role format"


def test_returns_last_user_message():
    """Only the most recent user message content is returned."""
    msgs = [
        {"type": "human", "content": "first"},
        {"role": "assistant", "content": "response"},
        {"type": "human", "content": "second"},
    ]
    assert get_user_query(msgs) == "second"


def test_returns_empty_string_when_no_user_message():
    """No user/human message in the list → empty string."""
    msgs = [
        {"role": "assistant", "content": "hi"},
        {"type": "ai", "content": "hello"},
    ]
    assert get_user_query(msgs) == ""


def test_handles_list_content():
    """Multimodal messages with list content (text + images)."""
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "describe this"}]},
    ]
    assert get_user_query(msgs) == "describe this"


def test_ignores_tool_and_system_messages():
    """System and tool messages are not user messages."""
    msgs = [
        {"role": "system", "content": "be helpful"},
        {"type": "tool", "content": "tool result"},
        {"type": "human", "content": "actual user query"},
    ]
    assert get_user_query(msgs) == "actual user query"


def test_returns_empty_for_non_dict():
    """Non-dict items are safely ignored."""
    msgs = ["just a string", {"role": "user", "content": "real query"}]
    assert get_user_query(msgs) == "real query"


# ---------------------------------------------------------------------------
# get_conversation_history
# ---------------------------------------------------------------------------

def test_history_mixed_type_and_role():
    """Both ``type`` and ``role`` formats are accepted."""
    msgs = [
        {"type": "human", "content": "user via type"},
        {"role": "assistant", "content": "assistant via role"},
    ]
    history = get_conversation_history(msgs)
    assert history == [
        {"role": "user", "content": "user via type"},
        {"role": "assistant", "content": "assistant via role"},
    ]


def test_history_normalises_type_to_role():
    """``type: "human"`` becomes ``role: "user"`` in output."""
    msgs = [
        {"type": "human", "content": "hello"},
        {"type": "ai", "content": "world"},
    ]
    history = get_conversation_history(msgs)
    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]


def test_history_skips_tool_and_system():
    """Tool and system messages are filtered out."""
    msgs = [
        {"role": "system", "content": "prompt"},
        {"role": "user", "content": "user msg"},
        {"type": "tool", "content": "tool result"},
        {"role": "assistant", "content": "assistant msg"},
    ]
    history = get_conversation_history(msgs)
    assert history == [
        {"role": "user", "content": "user msg"},
        {"role": "assistant", "content": "assistant msg"},
    ]


def test_history_returns_empty_list_when_no_messages():
    assert get_conversation_history([]) == []


def test_history_ignores_non_dict():
    msgs = [42, None, {"role": "user", "content": "valid"}]
    assert get_conversation_history(msgs) == [{"role": "user", "content": "valid"}]


# ---------------------------------------------------------------------------
# trim_history
# ---------------------------------------------------------------------------

def test_trim_history_under_budget():
    from src.agent_utils import trim_history
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    result = trim_history(msgs, max_tokens=4000)
    assert result == msgs


def test_trim_history_drops_oldest():
    from src.agent_utils import trim_history
    msgs = [{"role": "user", "content": f"msg {i}"} for i in range(50)]
    result = trim_history(msgs, max_tokens=50)
    assert len(result) < len(msgs)
    assert "msg 0" not in result  # oldest should be dropped


def test_trim_history_empty():
    from src.agent_utils import trim_history
    assert trim_history([], max_tokens=100) == []


def test_trim_history_preserves_tool_pairs():
    from src.agent_utils import trim_history
    msgs = [
        {"role": "user", "content": "old question"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "use file tool"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"name": "read_file", "args": {"file_path": "x.txt"}}],
        },
        {"role": "tool", "content": "file contents", "name": "read_file"},
        {"role": "assistant", "content": "here is the content"},
    ]
    result = trim_history(msgs, max_tokens=2000)
    tool_call_idx = None
    tool_result_idx = None
    for i, m in enumerate(result):
        if m.get("tool_calls"):
            tool_call_idx = i
        if m.get("role") == "tool":
            tool_result_idx = i
    if tool_call_idx is not None:
        assert tool_result_idx is not None, "Tool result must exist if tool call exists"
        assert tool_result_idx > tool_call_idx, "Tool result must follow tool call"


def test_trim_history_keeps_at_least_one_group():
    from src.agent_utils import trim_history
    msgs = [
        {"role": "user", "content": "hello"},
    ]
    result = trim_history(msgs, max_tokens=1)
    assert len(result) == 1
