from dataclasses import dataclass
from pathlib import Path
from typing import List



IGNORED_DIRS = {".git", "node_modules", "__pycache__",".venv", "venv"}

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".java", ".go", ".rb", ".md"}


@dataclass
class CodeChunk:
    file_path: str
    content: str
    start_line: str
    end_line: str


def parse_repo(repo_path: Path) -> List[CodeChunk]:

    chunks: List[CodeChunk] = []

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        if any(part in IGNORED_DIRS for part in file_path.parts):
            continue

        if file_path.suffix not in SOURCE_EXTENSIONS:
            continue

        content = file_path.read_text(errors="ignore")
        line_count = content.count("\n") + 1


        chunks.append(
            CodeChunk(
                file_path=str(file_path.relative_to(repo_path)),
                content=content,
                start_line=1,
                end_line=line_count,
            )
        )

    return chunks

