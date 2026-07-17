from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated, List
import operator
import os
import subprocess
import re
from src.llm import get_opencode_llm, OPENCODE_MODEL


class State(TypedDict):
    messages: Annotated[List[dict], operator.add]
    code_response: str
    reasoning: str


SYSTEM_PROMPT = f"""You are OpenCode CLI, an autonomous coding agent specialized in software engineering tasks.

Model in use: {OPENCODE_MODEL}

Your capabilities:
1. Write clean, idiomatic, working code.
2. Debug errors by analyzing stack traces and suggesting precise fixes.
3. Review code for correctness, performance, security, and maintainability.
4. Design system architecture and explain trade-offs.
5. Run shell commands in the user's workspace when explicitly allowed.

Rules:
- Always wrap code blocks in triple backticks with the language tag.
- Provide concise explanations before or after code, not inside it.
- If the request is ambiguous, ask clarifying questions.
- Never execute destructive commands (rm -rf, format drives, etc.).
- Prefer safe, reversible edits.
- When suggesting file changes, show the full file path in a comment on the first line.

Response format:
1. Brief plan or reasoning in plain text.
2. Code blocks for any files, scripts, or commands.
3. Final summary of what was done."""


ALLOWED_COMMANDS = [
    "python",
    "python3",
    "pytest",
    "npm",
    "npx",
    "node",
    "git",
    "pip",
    "ls",
    "cat",
    "mkdir",
    "cp",
    "mv",
    "curl",
]


def _extract_shell_commands(text: str) -> list[str]:
    """Extract shell commands from markdown code blocks labeled 'bash' or 'shell'."""
    pattern = r"```(?:bash|shell|zsh)\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [cmd.strip() for cmd in matches if cmd.strip()]


def _is_safe_command(command: str) -> bool:
    """Check if a command starts with an allowed executable."""
    tokens = command.split()
    if not tokens:
        return False
    return tokens[0] in ALLOWED_COMMANDS


def _run_command(command: str, cwd: str = None) -> str:
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout.strip() or "(no output)"
        if result.returncode != 0:
            output += f"\n\n[error] {result.stderr.strip() or '(no stderr)'}"
        return output
    except subprocess.TimeoutExpired:
        return "[error] command timed out after 60s"
    except Exception as e:
        return f"[error] {e}"


def opencode_coding_agent(state: State):
    """OpenCode CLI agent - powered by Ollama Cloud"""
    messages = state["messages"]
    user_query = ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            user_query = m.get("content", "")
            break

    llm = get_opencode_llm()

    langchain_messages = [
        ("system", SYSTEM_PROMPT),
        ("human", user_query),
    ]

    try:
        response = llm.invoke(langchain_messages)
        content = response.content

        # Optional: auto-run safe shell commands found in the response
        auto_run_enabled = os.getenv("OPENCODE_AUTO_RUN", "false").lower() == "true"
        if auto_run_enabled:
            workspace = os.getenv("OPENCODE_WORKSPACE", os.getcwd())
            commands = _extract_shell_commands(content)
            for cmd in commands:
                if _is_safe_command(cmd):
                    output = _run_command(cmd, cwd=workspace)
                    content += f"\n\n---\nRan `{cmd}`:\n```\n{output}\n```"

        return {
            "messages": [{"role": "assistant", "content": content}],
            "code_response": content,
            "reasoning": "executed single-turn coding agent",
        }
    except Exception as e:
        error_msg = f"""[OpenCode CLI Agent]

Error: {str(e)}

Please verify your Ollama Cloud API key and model in `backend/.env`:
```env
LLM_BASE_URL=https://ollama.com
LLM_API_KEY=<your-key>
OPENCODE_MODEL=qwen3.5:397b
```"""
        return {
            "messages": [{"role": "assistant", "content": error_msg}],
            "code_response": error_msg,
            "reasoning": "error",
        }


def create_opencode_graph():
    graph = StateGraph(State)
    graph.add_node("opencode_agent", opencode_coding_agent)
    graph.add_edge(START, "opencode_agent")
    graph.add_edge("opencode_agent", END)
    return graph.compile()


if __name__ == "__main__":
    app = create_opencode_graph()
    result = app.invoke({"messages": [{"role": "user", "content": "Create a hello world function"}]})
    print(result["code_response"])
