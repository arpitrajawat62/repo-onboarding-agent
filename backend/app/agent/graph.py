import json
import re
import time
from openai import OpenAI, BadRequestError, RateLimitError, APIConnectionError

from app.config import settings
from app.agent.prompts import (
    PLANNER_SYSTEM_PROMPT,
    build_planner_user_prompt,
    CONFIDENCE_SYSTEM_PROMPT,
    build_confidence_user_prompt,
    SYNTHESIZER_SYSTEM_PROMPT,
    build_synthesizer_user_prompt,
)
from app.agent.state import AgentState, Finding
from app.agent.tools import list_dir, read_file, search_code

from langgraph.graph import StateGraph, END


_llm_client = OpenAI(
    api_key=settings.gemini_api_key,
    base_url=settings.gemini_base_url,
)


def _chat(messages: list, json_mode: bool = False, name: str = "llm", retries: int = 4):
    """One LLM call. Waits and retries when the provider says we're going too fast."""
    kwargs = {"model": settings.gemini_model, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return _llm_client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            last_error = e
            wait = 5 * attempt
            print(f"  [{name}] rate limited, waiting {wait}s (attempt {attempt}/{retries})")
            time.sleep(wait)
        except APIConnectionError as e:
            last_error = e
            print(f"  [{name}] connection problem (attempt {attempt}/{retries}): {e.__cause__!r}")
            time.sleep(2)

    cause = repr(getattr(last_error, "__cause__", None) or last_error)
    raise RuntimeError(f"The LLM call '{name}' failed after {retries} attempts: {cause}")


def _coverage_note(findings: list) -> str:
    """Lists files the agent only read part of, using the 'file continues' markers."""
    partial = {}

    for f in findings:
        if f["action"] != "read_file":
            continue
        path = f["target"].split(" (from character")[0]
        match = re.search(r"showing characters (\d+)-(\d+) of (\d+)", f["result_summary"])
        if match:
            partial[path] = (int(match.group(2)), int(match.group(3)))
        else:
            partial.pop(path, None)

    if not partial:
        return ""

    lines = [
        f"- {path}: read {end} of {total} characters"
        for path, (end, total) in partial.items()
    ]
    return (
        "\n\n---\nCoverage note: the agent read only part of these files, so anything "
        "said about their unread parts is not based on the code it saw:\n"
        + "\n".join(lines)
    )


def _ask_for_json(system_prompt: str, user_prompt: str, name: str = "llm", retries: int = 5) -> dict:
    """
    Calls the LLM expecting a JSON object back. Retries on empty or
    invalid replies. Returns {} if every attempt fails.
    """
    for attempt in range(1, retries + 1):
        try:
            response = _chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                json_mode=True,
                name=name,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            if not raw_text:
                print(f"  [{name}] attempt {attempt}: empty reply")
                continue
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                return parsed

        except (BadRequestError, json.JSONDecodeError) as e:
            detail = getattr(e, "body", None)
            if isinstance(detail, dict) and "failed_generation" in detail:
                detail = f"failed_generation={detail['failed_generation']!r}"
            print(f"  [{name}] attempt {attempt} failed: {str(detail or e)[:500]}")

    print(f"WARNING: no usable JSON from the LLM in '{name}' after retries")
    return {}


def explorer_node(state: AgentState) -> AgentState:
    action = state["next_action"]
    tool_name = action.get("tool")
    arg = action.get("arg", "")
    repo_id = state["repo_id"]

    try:
        start = int(action.get("start", 0))
    except (TypeError, ValueError):
        start = 0

    target = arg

    if tool_name == "list_dir":
        result = list_dir(repo_id, arg)
        result_summary = f"Contents: {result}"

    elif tool_name == "read_file":
        result_summary = read_file(repo_id, arg, start=start)
        if start:
            target = f"{arg} (from character {start})"

    elif tool_name == "search_code":
        result = search_code(repo_id, arg)
        matched = [r["file_path"].replace("\\", "/") for r in result[:3]]
        result_summary = "Matched files: " + " | ".join(matched) + "\n\n" + "\n".join(
            f"  {r['file_path']}: {r['content'][:300]}" for r in result[:3]
        )

    else:
        result_summary = f"(unknown tool: {tool_name})"

    finding: Finding = {
        "action": tool_name,
        "target": target,
        "result_summary": result_summary,
    }

    state["findings"].append(finding)
    state["steps_taken"] += 1
    return state


def planner_node(state: AgentState) -> AgentState:
    """
    Asks the LLM to decide the next exploration action, based on the
    question and findings accumulated so far.
    """
    user_prompt = build_planner_user_prompt(state["question"], state["findings"])

    next_action = _ask_for_json(PLANNER_SYSTEM_PROMPT, user_prompt, name="planner")

    if not next_action.get("tool"):
        next_action = {"tool": "list_dir", "arg": "."}

    state["next_action"] = next_action
    return state


MAX_STEP = 8


def confidence_node(state: AgentState) -> AgentState:
    """
    Asks the LLM whether findings so far are enough to answer the
    question, or whether more exploration is needed.
    """
    if state["steps_taken"] >= MAX_STEP:
        state["confident_enough"] = True
        return state

    has_read_a_file = any(f["action"] == "read_file" for f in state["findings"])
    if not has_read_a_file:
        state["confident_enough"] = False
        return state

    user_prompt = build_confidence_user_prompt(state["question"], state["findings"])
    result = _ask_for_json(CONFIDENCE_SYSTEM_PROMPT, user_prompt, name="confidence")
    state["confident_enough"] = result.get("confident", False)

    return state


def synthesizer_node(state: AgentState) -> AgentState:
    """
    Writes the final answer from all accumulated findings.
    """
    user_prompt = build_synthesizer_user_prompt(state["question"], state["findings"])

    response = _chat(
        [
            {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        name="synthesizer",
    )

    answer = (response.choices[0].message.content or "").strip()
    state["final_answer"] = answer + _coverage_note(state["findings"])
    return state


def _route_after_confidence(state: AgentState) -> str:
    """
    Decides where to go after the confidence check: back to planner
    for another round of exploration, or on to the synthesizer.
    """
    if state["confident_enough"]:
        return "synthesizer"
    return "planner"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("explorer", explorer_node)
    graph.add_node("confidence", confidence_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "explorer")
    graph.add_edge("explorer", "confidence")
    graph.add_conditional_edges(
        "confidence",
        _route_after_confidence,
        {"planner": "planner", "synthesizer": "synthesizer"},
    )
    graph.add_edge("synthesizer", END)

    return graph.compile()