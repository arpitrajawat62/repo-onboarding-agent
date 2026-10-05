from app.agent.state import AgentState, Finding
from app.agent.tools import list_dir, read_file, search_code



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
