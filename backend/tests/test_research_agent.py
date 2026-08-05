from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src import research_agent


def test_research_agent_is_built_with_read_only_evidence_tools(tmp_path):
    model = MagicMock()

    with patch.object(research_agent, "create_deep_agent") as create_agent:
        research_agent.create_research_agent(model, workspace=str(tmp_path))

    kwargs = create_agent.call_args.kwargs
    assert kwargs["model"] is model
    assert [tool.name for tool in kwargs["tools"]] == [
        "web_search",
        "read_url",
        "ingest_uploaded_sources",
        "read_workspace_source",
        "read_saved_source",
    ]
    assert all(permission.mode != "allow" or "write" not in permission.operations for permission in kwargs["permissions"])
    assert kwargs["name"] == "research"


@pytest.mark.asyncio
async def test_standalone_research_profile_passes_selected_context_and_returns_findings(tmp_path):
    model = MagicMock()
    agent = MagicMock()
    agent.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content="Grounded findings with evidence web-456.")]
    })

    with (
        patch.object(research_agent, "get_agent_llm", return_value=model) as get_model,
        patch.object(
            research_agent, "create_research_agent", return_value=agent
        ) as create_specialist,
    ):
        result = await research_agent.research_agent(
            {
                "messages": [{"role": "user", "content": "Research SIFT"}],
                "model": "ollama-cloud/glm-5.2",
                "workspace": str(tmp_path),
            }
        )

    get_model.assert_called_once_with("ollama-cloud/glm-5.2")
    create_specialist.assert_called_once_with(model, workspace=str(tmp_path), store=None)
    assert result["research_findings"] == "Grounded findings with evidence web-456."
