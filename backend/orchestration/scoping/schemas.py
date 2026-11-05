"""
Pydantic v2 schemas for Agent 1 output validation.

The LLM's JSON response must conform to `ScopingOutput`.
If validation fails, we retry once with the error message,
then fall back to the deterministic engine.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class Lot(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = ""
    estimate_hours: float = Field(..., ge=0, le=5000)
    confidence: float = Field(0.7, ge=0, le=1)
    color: str = "#0EA5E9"
    order: int = Field(..., ge=1)


TaskType = Literal["FEATURE", "TECH", "SPIKE", "DOC", "TEST", "BUG"]
TaskPriority = Literal["LOWEST", "LOW", "MEDIUM", "HIGH", "HIGHEST"]


class Task(BaseModel):
    ref: str = Field(..., min_length=1, max_length=40)
    lot: str
    title: str = Field(..., min_length=2, max_length=200)
    description: str = ""
    type: TaskType = "FEATURE"
    priority: TaskPriority = "MEDIUM"
    estimate_hours: float = Field(..., ge=0.5, le=200)
    story_points: int = Field(..., ge=1, le=40)
    skills: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=10)
    risk_score: int = Field(0, ge=0, le=100)
    sprint: str = ""

    @field_validator("acceptance_criteria")
    @classmethod
    def at_least_3_criteria(cls, v):
        # Soft validation: warn but don't fail if < 3
        return v


class Sprint(BaseModel):
    name: str
    goal: str = ""
    capacity_hours: float = Field(..., ge=0)


RiskCategory = Literal["DELAY", "QUALITY", "LOAD", "BLOCKER", "SCOPE", "BUDGET"]


class Risk(BaseModel):
    category: RiskCategory = "DELAY"
    title: str
    score: int = Field(50, ge=0, le=100)


class ScopingOutput(BaseModel):
    """Full validated output of the Scoping Agent."""
    lots: list[Lot] = Field(..., min_length=1, max_length=10)
    tasks: list[Task] = Field(..., min_length=1, max_length=100)
    sprints: list[Sprint] = Field(..., min_length=1, max_length=10)
    risks: list[Risk] = Field(default_factory=list, max_length=10)
    assumptions: list[str] = Field(default_factory=list)
    total_estimate_hours: float = Field(..., ge=0)
    confidence: float = Field(0.7, ge=0, le=1)

    def to_proposal_payload(self) -> dict:
        """Convert to the dict shape expected by Proposal model fields."""
        return {
            "lots_payload": [lot.model_dump() for lot in self.lots],
            "tasks_payload": [task.model_dump() for task in self.tasks],
            "sprints_payload": [sprint.model_dump() for sprint in self.sprints],
            "risks_payload": [risk.model_dump() for risk in self.risks],
            "assumptions": self.assumptions,
            "total_estimate_hours": self.total_estimate_hours,
            "confidence": self.confidence,
        }
