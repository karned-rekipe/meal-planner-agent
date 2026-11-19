import fastmcp

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.planner_agent_schema import (
    SuggestItemRequestSchema,
    SuggestionSchema,
    WeekIndicatorsRequestSchema,
    WeekIndicatorsResponseSchema,
    WeekProposalRequestSchema,
    WeekProposalResponseSchema,
)
from application.services.planner_agent_service import PlannerAgentService
from application.services.planner_execution_recorder import PlannerExecutionRecorder
from arclith.domain.ports.logger import Logger


class PlannerAgentMCP:
    def __init__(
        self,
        service: PlannerAgentService,
        logger: Logger,
        mcp: fastmcp.FastMCP,
        recorder: PlannerExecutionRecorder | None = None,
    ) -> None:
        self._service = service
        self._logger = logger
        self._recorder = recorder
        self._register_tools(mcp)

    def _register_tools(self, mcp: fastmcp.FastMCP) -> None:
        service = self._service
        logger = self._logger

        @mcp.tool
        async def suggest_meal_plan_item(
            payload: SuggestItemRequestSchema,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Suggest 1 to 3 recipe candidates for a meal-plan slot."""
            await inject_tenant_uri(ctx)
            request = payload
            suggestions = await self._execute(
                name="suggest_meal_plan_item",
                payload=request.model_dump(mode="json"),
                operation=lambda: service.suggest_item(request.to_context()),
                serialize=lambda result: [SuggestionSchema.from_domain(item).model_dump(mode="json") for item in result],
            )
            logger.info("Meal-planner MCP item suggestions computed", count=len(suggestions))
            return {
                "suggestions": [
                    SuggestionSchema.from_domain(suggestion).model_dump(mode="json")
                    for suggestion in suggestions
                ]
            }

        @mcp.tool
        async def propose_meal_plan_week(
            payload: WeekProposalRequestSchema,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Propose a complete draft of lunch and dinner slots for a period."""
            await inject_tenant_uri(ctx)
            request = payload
            proposal = await self._execute(
                name="propose_meal_plan_week",
                payload=request.model_dump(mode="json"),
                operation=lambda: service.propose_week(request.to_context()),
                serialize=lambda result: WeekProposalResponseSchema.from_domain(result).model_dump(mode="json"),
            )
            logger.info(
                "Meal-planner MCP week proposal computed",
                slots=len(proposal.slots),
                coverage_rate=proposal.coverage_rate,
            )
            return WeekProposalResponseSchema.from_domain(proposal).model_dump(mode="json")

        @mcp.tool
        async def compute_meal_plan_week_indicators(
            payload: WeekIndicatorsRequestSchema,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Compute balance indicators for a proposed or existing week."""
            await inject_tenant_uri(ctx)
            request = payload
            indicators = await self._execute(
                name="compute_meal_plan_week_indicators",
                payload=request.model_dump(mode="json"),
                operation=lambda: service.compute_indicators(tuple(slot.to_domain() for slot in request.slots)),
                serialize=lambda result: WeekIndicatorsResponseSchema.from_domain(result).model_dump(mode="json"),
            )
            logger.info(
                "Meal-planner MCP indicators computed",
                planned_slots_count=indicators.planned_slots_count,
                recipe_count=indicators.recipe_count,
            )
            return WeekIndicatorsResponseSchema.from_domain(indicators).model_dump(mode="json")

    async def _execute(self, *, name: str, payload: dict, operation, serialize):
        if self._recorder is None:
            return operation()
        return await self._recorder.execute(
            name=name,
            input_payload=payload,
            transport="mcp",
            operation=operation,
            serialize=serialize,
        )
