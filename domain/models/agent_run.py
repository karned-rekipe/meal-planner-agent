from typing import Any, Literal

from pydantic import Field, field_validator

from arclith.domain.models.entity import Entity


class AgentRun(Entity):
    name: str = Field(
        ...,
        description="Nom de l'ingrédient",
        examples = ["Ingrédient 1", "Ingrédient 2"],
    )
    status: Literal["running", "success", "failed"] = "running"
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: Any | None = None
    duration_ms: int | None = None
    error: str | None = None
    transport: Literal["rest", "mcp"] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("AgentRun name cannot be empty")
        return stripped

