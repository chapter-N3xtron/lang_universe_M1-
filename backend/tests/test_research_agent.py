from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from src import research_agent


def test_research_agent_is_built_with_web_tools():
    model = MagicMock()

    with patch.object(research_agent, "create_agent") as create_agent:
        research_agent.create_research_agent(model)

    kwargs = create_agent.call_args.kwargs
    assert kwargs["model"] is model
    assert [tool.name for tool in kwargs["tools"]] == ["web_search", "read_url"]
    assert kwargs["name"] == "research"


def test_standalone_research_profile_passes_selected_model_and_returns_findings():
    model = MagicMock()
    agent = MagicMock()
    agent.invoke.return_value = {
        "messages": [AIMessage(content="Grounded findings with evidence web-456.")]
    }

    with (
        patch.object(research_agent, "get_agent_llm", return_value=model) as get_model,
        patch.object(
            research_agent, "create_research_agent", return_value=agent
        ) as create_specialist,
    ):
        result = research_agent.research_agent(
            {
                "messages": [{"role": "user", "content": "Research SIFT"}],
                "model": "ollama-cloud/glm-5.2",
            }
        )

    get_model.assert_called_once_with("ollama-cloud/glm-5.2")
    create_specialist.assert_called_once_with(model)
    assert result["research_findings"] == "Grounded findings with evidence web-456."
