from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.planner_agent_schema import (
    SuggestItemRequestSchema,
    SuggestItemResponseSchema,
    SuggestionSchema,
    WeekIndicatorsRequestSchema,
    WeekIndicatorsResponseSchema,
    WeekProposalRequestSchema,
    WeekProposalResponseSchema,
)
from application.services.planner_agent_service import PlannerAgentService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import ApiResponse, ResponseMetadata, success_response
from arclith.domain.ports.logger import Logger


class PlannerAgentRouter:
    def __init__(self, service: PlannerAgentService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix="/v1/agent/meal-plans",
            tags=["meal-planner-agent"],
            dependencies=[Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods=["POST"],
            path="/suggest-item",
            endpoint=self.suggest_item,
            summary="Suggest recipes for one meal-plan slot",
            response_model=ApiResponse[SuggestItemResponseSchema],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/propose-week",
            endpoint=self.propose_week,
            summary="Propose a complete meal-plan draft for a period",
            response_model=ApiResponse[WeekProposalResponseSchema],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/indicators",
            endpoint=self.week_indicators,
            summary="Compute weekly balance indicators for a meal plan",
            response_model=ApiResponse[WeekIndicatorsResponseSchema],
            status_code=200,
        )

    async def suggest_item(
        self,
        payload: SuggestItemRequestSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[SuggestItemResponseSchema]:
        suggestions = self._service.suggest_item(payload.to_context())
        self._logger.info("Meal-planner agent suggestions computed", count=len(suggestions))
        return success_response(
            SuggestItemResponseSchema(
                suggestions=[SuggestionSchema.from_domain(suggestion) for suggestion in suggestions],
            ),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def propose_week(
        self,
        payload: WeekProposalRequestSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[WeekProposalResponseSchema]:
        try:
            proposal = self._service.propose_week(payload.to_context())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        self._logger.info(
            "Meal-planner agent week proposal computed",
            slots=len(proposal.slots),
            coverage_rate=proposal.coverage_rate,
        )
        return success_response(
            WeekProposalResponseSchema.from_domain(proposal),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def week_indicators(
        self,
        payload: WeekIndicatorsRequestSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[WeekIndicatorsResponseSchema]:
        indicators = self._service.compute_indicators(tuple(slot.to_domain() for slot in payload.slots))
        self._logger.info(
            "Meal-planner agent indicators computed",
            planned_slots_count=indicators.planned_slots_count,
            recipe_count=indicators.recipe_count,
        )
        return success_response(
            WeekIndicatorsResponseSchema.from_domain(indicators),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )
