"""Output contract for rubric parsing.

The parser turns an arbitrary rubric file into this exact JSON shape:

    {"rubric": [
        {"parameter_title": "...", "description": "...", "points": 10},
        {"parameter_title": "...", "description": "..."}            # points optional
    ]}

Kept dependency-free (dataclasses + stdlib) so this folder stays self-contained
and does not pull in the backend's pydantic stack.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RubricCriterion:
    """One row of a rubric: a titled grading parameter with a description.

    `points` is optional because not every rubric assigns weights.
    """

    parameter_title: str
    description: str
    points: float | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "parameter_title": self.parameter_title,
            "description": self.description,
        }
        if self.points is not None:
            out["points"] = self.points
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RubricCriterion":
        if not isinstance(data, dict):
            raise ValueError(f"criterion must be an object, got {type(data).__name__}")

        title = data.get("parameter_title")
        description = data.get("description")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("criterion is missing a non-empty 'parameter_title'")
        if not isinstance(description, str):
            raise ValueError(f"criterion '{title}' is missing a string 'description'")

        points = data.get("points")
        if points is not None:
            try:
                points = float(points)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"criterion '{title}' has non-numeric points: {points!r}"
                ) from exc

        return cls(
            parameter_title=title.strip(),
            description=description.strip(),
            points=points,
        )


@dataclass
class Rubric:
    """A parsed rubric: an ordered list of criteria."""

    rubric: list[RubricCriterion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"rubric": [c.to_dict() for c in self.rubric]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Rubric":
        if not isinstance(data, dict) or "rubric" not in data:
            raise ValueError("payload must be an object with a top-level 'rubric' key")
        rows = data["rubric"]
        if not isinstance(rows, list):
            raise ValueError("'rubric' must be a list of criteria")
        return cls(rubric=[RubricCriterion.from_dict(row) for row in rows])
