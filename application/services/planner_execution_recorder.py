from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any, Literal, TypeVar

from application.services.agent_run_service import AgentRunService
from domain.models.agent_run import AgentRun

Result = TypeVar("Result")


class PlannerExecutionRecorder:
    """Persist the lifecycle of an agent operation without polluting its scoring core."""

    def __init__(self, agent_runs: AgentRunService) -> None:
        self._agent_runs = agent_runs

    async def execute(
        self,
        *,
        name: str,
        input_payload: dict[str, Any],
        transport: Literal["rest", "mcp"],
        operation: Callable[[], Result],
        serialize: Callable[[Result], Any],
    ) -> Result:
        run = await self._agent_runs.create(
            AgentRun(name=name, input_payload=input_payload, transport=transport)
        )
        started_at = perf_counter()
        try:
            result = operation()
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            run.duration_ms = round((perf_counter() - started_at) * 1000)
            await self._agent_runs.update(run)
            raise

        run.status = "success"
        run.output_payload = serialize(result)
        run.duration_ms = round((perf_counter() - started_at) * 1000)
        await self._agent_runs.update(run)
        return result
