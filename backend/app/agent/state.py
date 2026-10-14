from typing import TypedDict, List, Dict, Any


class Finding(TypedDict):
    action: str
    target: str
    result_summary: str


class AgentState(TypedDict):
    repo_id: str
    question: str

    findings: List[Finding]
    steps_taken: int

    next_action: Dict[str, Any]
    confident_enough: bool

    final_answer: str
    