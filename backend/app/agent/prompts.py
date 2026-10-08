"""
Prompt templates for the agent's LLM calls. Kept separate from
graph.py so wording can be iterated on without touching control flow.
"""

PLANNER_SYSTEM_PROMPT = """You are an expert software engineer exploring an unfamiliar codebase.
Your job is to decide the SINGLE next action to take to help answer the user's question.


Available tools:
- list_dir: list files/folders at a path. arg = folder path (use "." for root)
- read_file: read a file's contents. arg = file path
- search_code: semantically search the codebase. arg = a natural language query

Respond with ONLY a JSON object in this exact shape, nothing else:
{"tool": "<tool_name>", "arg": "<argument>"}
"""


def build_planner_user_prompt(question: str, findings: list) -> str:
    findings_text = "\n".join(
        f"- {f['action']}({f['target']}): {f['result_summary']}" for f in findings
    ) or "(nothing explored yet)"

    return f"""Question: {question}
    
Finding so far:
{findings_text}

what is the single next action to take? """


# Confidence prompt

CONFIDENCE_SYSTEM_PROMPT = """You are an expert software engineer judging whether enough
information has been gathered to answer a question about a codebase.

Respond with ONLY a JSON object in this exact shape, nothing else:
{"confident": true} or {"confident": false}

Say true only if the findings so far genuinely answer the question.
Say false if more exploration is needed.
"""


def build_confidence_user_prompt(question: str, findings: list) -> str:
    findings_text = "\n".join(
        f"- {f['action']}({f['target']}): {f['result_summary']}" for f in findings
    )  or "(nothing explored yet)"

    return f"""Question: {question}

Findings so far:
{findings_text}

Is this enough to ans the question?"""



# Synthesizer prompt

SYNTHESIZER_SYSTEM_PROMPT = """You are an expert software engineer explaining a codebase
to a new team member. Write a clear, well-organized answer to their question, based
ONLY on the findings provided below.

Do NOT invent file contents, code snippets, or implementation details that are not
explicitly present in the findings. If the findings are insufficient to fully answer
the question, say so clearly and explain what additional information would be needed,
rather than guessing or fabricating specifics.
"""

def build_synthesizer_user_prompt(question: str, findings: list) -> str:
    finding_text = "\n".join(
        f"- {f['action']}({f['target']}): {f['result_summary']}" for f in findings
    )  or "(nothing explored)"

    return f"""Question: {question}

Findings:
{finding_text}


Write the final answer."""
