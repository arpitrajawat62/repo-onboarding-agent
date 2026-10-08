import json 
from groq import Groq

from app.config import settings
from app.agent.prompts import (
    PLANNER_SYSTEM_PROMPT, 
    build_planner_user_prompt, 
    CONFIDENCE_SYSTEM_PROMPT,
    build_confidence_user_prompt,
    SYNTHESIZER_SYSTEM_PROMPT, 
    build_synthesizer_user_prompt
)
from app.agent.state import AgentState, Finding
from app.agent.tools import list_dir, read_file, search_code

from langgraph.graph import StateGraph, END


_groq_client = Groq(api_key=settings.groq_api_key)

def explorer_node(state: AgentState) -> AgentState:

    action = state["next_action"] 
    tool_name = action.get("tool")
    arg = action.get("arg", "")
    repo_id = state["repo_id"]

    if tool_name == "list_dir":
        result = list_dir(repo_id, arg)
        result_summary = f"Contents: {result}"

    elif tool_name == "read_file":
        result = read_file(repo_id, arg)
        result_summary = result[:300]

    elif tool_name == "search_code":
        result = search_code(repo_id, arg)
        result_summary = f"Found in: {[r["file_path"] for r in result]}"

    else:
        result_summary = f"(unknown tool: {tool_name})"


    finding: Finding = {
        "action": tool_name,
        "target": arg,
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

    response = _groq_client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw_text = (response.choices[0].message.content or "").strip()

    if not raw_text:
        next_action = {"tool": "list_dir", "arg": "."}
    else:
        next_action = json.loads(raw_text)


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

    user_prompt = build_confidence_user_prompt(state["question"], state["findings"])


    response = _groq_client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": CONFIDENCE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw_text = (response.choices[0].message.content or "").strip()

    if not raw_text:
        state["confident_enough"] = False
    else:
        result = json.loads(raw_text)
        state["confident_enough"] = result.get("confident", False)

    return state



def synthesizer_node(state: AgentState) -> AgentState:
    """
    Writes the final answer from all accumulated findings.
    """
    user_prompt = build_synthesizer_user_prompt(state["question"], state["findings"])


    response = _groq_client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    state["final_answer"] = (response.choices[0].message.content or "").strip()
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