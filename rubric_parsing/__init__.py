"""rubric_parsing — convert an arbitrary rubric file into structured JSON.

Pipeline: file -> text (PyMuPDF for PDF / plaintext off disk) -> LLM extraction
-> validated `{"rubric": [{"parameter_title", "description", "points"?}, ...]}`.

Example:
    from rubric_parsing import parse_rubric_file
    rubric = parse_rubric_file("my_rubric.pdf")
    print(rubric.to_dict())
"""
from .extract import ExtractError, to_text
from .llm import LLMConfig, LLMConfigError, LLMRequestError
from .parser import parse_rubric_file, parse_rubric_text
from .schemas import Rubric, RubricCriterion

__all__ = [
    "parse_rubric_file",
    "parse_rubric_text",
    "to_text",
    "Rubric",
    "RubricCriterion",
    "LLMConfig",
    "LLMConfigError",
    "LLMRequestError",
    "ExtractError",
]
