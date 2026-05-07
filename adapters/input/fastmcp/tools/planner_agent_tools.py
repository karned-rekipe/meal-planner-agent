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
from arclith.domain.ports.logger import Logger


class PlannerAgentMCP:
    def __init__(self, service: PlannerAgentService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._logger = logger
        self._register_tools(mcp)

    def _register_tools(self, mcp: fastmcp.FastMCP) -> None:
        service = self._service
        logger = self._logger

        @mcp.tool
        async def suggest_meal_plan_item(payload: dict, ctx: fastmcp.Context | None = None) -> dict:
            """Suggest 1 to 3 recipe candidates for a meal-plan slot."""
            await inject_tenant_uri(ctx)
            request = SuggestItemRequestSchema.model_validate(payload)
            suggestions = service.suggest_item(request.to_context())
            logger.info("Meal-planner MCP item suggestions computed", count=len(suggestions))
            return {
                "suggestions": [
                    SuggestionSchema.from_domain(suggestion).model_dump(mode="json")
                    for suggestion in suggestions
                ]
            }

        @mcp.tool
        async def propose_meal_plan_week(payload: dict, ctx: fastmcp.Context | None = None) -> dict:
            """Propose a complete draft of lunch and dinner slots for a period."""
            await inject_tenant_uri(ctx)
            request = WeekProposalRequestSchema.model_validate(payload)
            proposal = service.propose_week(request.to_context())
            logger.info(
                "Meal-planner MCP week proposal computed",
                slots=len(proposal.slots),
                coverage_rate=proposal.coverage_rate,
            )
            return WeekProposalResponseSchema.from_domain(proposal).model_dump(mode="json")

        @mcp.tool
        async def compute_meal_plan_week_indicators(payload: dict, ctx: fastmcp.Context | None = None) -> dict:
            """Compute balance indicators for a proposed or existing week."""
            await inject_tenant_uri(ctx)
            request = WeekIndicatorsRequestSchema.model_validate(payload)
            indicators = service.compute_indicators(tuple(slot.to_domain() for slot in request.slots))
            logger.info(
                "Meal-planner MCP indicators computed",
                planned_slots_count=indicators.planned_slots_count,
                recipe_count=indicators.recipe_count,
            )
            return WeekIndicatorsResponseSchema.from_domain(indicators).model_dump(mode="json")
