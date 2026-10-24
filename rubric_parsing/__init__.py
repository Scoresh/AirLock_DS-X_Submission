"""rubric_parsing — convert an arbitrary rubric file into structured JSON.

Pipeline: file -> Markdown (libdump/pandoc.exe) -> LLM extraction -> validated
`{"rubric": [{"parameter_title", "description", "points"?}, ...]}`.

Example:
    from rubric_parsing import parse_rubric_file
    rubric = parse_rubric_file("my_rubric.docx")
    print(rubric.to_dict())
"""
from .llm import LLMConfig, LLMConfigError, LLMRequestError
from .pandoc import PandocError, to_markdown
from .parser import parse_rubric_file, parse_rubric_text
from .schemas import Rubric, RubricCriterion

__all__ = [
    "parse_rubric_file",
    "parse_rubric_text",
    "to_markdown",
    "Rubric",
    "RubricCriterion",
    "LLMConfig",
    "LLMConfigError",
    "LLMRequestError",
    "PandocError",
]
