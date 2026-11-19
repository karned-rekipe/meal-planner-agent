from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from domain.models.planner_agent import (
    CandidateRecipe,
    IndicatorSlot,
    SlotProposal,
    SuggestionContext,
    SuggestionResult,
    WeekIndicators,
    WeekProposal,
    WeekProposalContext,
)

SlotCode = Literal["lunch", "dinner"]


class CandidateRecipeSchema(BaseModel):
    recipe_uuid: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    season_months: list[int] = Field(default_factory=list)
    ingredient_uuids: list[str] = Field(default_factory=list)
    ingredient_names: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    green_score: float | None = Field(default=None, ge=0, le=100)

    @field_validator("season_months")
    @classmethod
    def validate_months(cls, value: list[int]) -> list[int]:
        invalid = [month for month in value if month < 1 or month > 12]
        if invalid:
            raise ValueError("season_months must contain values from 1 to 12")
        return sorted(set(value))

    def to_domain(self) -> CandidateRecipe:
        return CandidateRecipe(
            recipe_uuid=self.recipe_uuid,
            title=self.title,
            season_months=tuple(self.season_months),
            ingredient_uuids=tuple(self.ingredient_uuids),
            ingredient_names=tuple(self.ingredient_names),
            groups=tuple(self.groups),
            green_score=self.green_score,
        )


class SuggestItemRequestSchema(BaseModel):
    slot_date: date
    slot_code: SlotCode
    headcount: int = Field(default=2, ge=0, le=50)
    candidates: list[CandidateRecipeSchema] = Field(default_factory=list)
    fridge_ingredient_uuids: list[str] = Field(default_factory=list)
    fridge_terms: list[str] = Field(default_factory=list)
    excluded_recipe_uuids: list[str] = Field(default_factory=list)
    excluded_ingredient_uuids: list[str] = Field(default_factory=list)
    excluded_groups: list[str] = Field(default_factory=list)
    recent_recipe_uuids: list[str] = Field(default_factory=list)
    max_suggestions: int = Field(default=3, ge=1, le=10)

    def to_context(self) -> SuggestionContext:
        return SuggestionContext(
            slot_date=self.slot_date,
            slot_code=self.slot_code,
            headcount=self.headcount,
            candidates=tuple(candidate.to_domain() for candidate in self.candidates),
            fridge_ingredient_uuids=tuple(self.fridge_ingredient_uuids),
            fridge_terms=tuple(self.fridge_terms),
            excluded_recipe_uuids=tuple(self.excluded_recipe_uuids),
            excluded_ingredient_uuids=tuple(self.excluded_ingredient_uuids),
            excluded_groups=tuple(self.excluded_groups),
            recent_recipe_uuids=tuple(self.recent_recipe_uuids),
            max_suggestions=self.max_suggestions,
        )


class SuggestionSchema(BaseModel):
    recipe_uuid: str
    title: str
    score: float
    reason_codes: list[str]
    reason: str

    @classmethod
    def from_domain(cls, suggestion: SuggestionResult) -> "SuggestionSchema":
        return cls(
            recipe_uuid=suggestion.recipe_uuid,
            title=suggestion.title,
            score=suggestion.score,
            reason_codes=list(suggestion.reason_codes),
            reason=suggestion.reason,
        )


class SuggestItemResponseSchema(BaseModel):
    suggestions: list[SuggestionSchema]


class WeekProposalRequestSchema(BaseModel):
    date_start: date
    date_end: date
    default_headcount: int = Field(default=2, ge=0, le=50)
    candidates: list[CandidateRecipeSchema] = Field(default_factory=list)
    fridge_ingredient_uuids: list[str] = Field(default_factory=list)
    fridge_terms: list[str] = Field(default_factory=list)
    excluded_recipe_uuids: list[str] = Field(default_factory=list)
    excluded_ingredient_uuids: list[str] = Field(default_factory=list)
    excluded_groups: list[str] = Field(default_factory=list)
    recent_recipe_uuids: list[str] = Field(default_factory=list)
    max_reuse_per_recipe: int = Field(default=1, ge=1, le=14)

    @model_validator(mode="after")
    def validate_period(self) -> "WeekProposalRequestSchema":
        if self.date_end < self.date_start:
            raise ValueError("date_end must be greater than or equal to date_start")
        if (self.date_end - self.date_start).days + 1 > 31:
            raise ValueError("period cannot exceed 31 days")
        return self

    def to_context(self) -> WeekProposalContext:
        return WeekProposalContext(
            date_start=self.date_start,
            date_end=self.date_end,
            default_headcount=self.default_headcount,
            candidates=tuple(candidate.to_domain() for candidate in self.candidates),
            fridge_ingredient_uuids=tuple(self.fridge_ingredient_uuids),
            fridge_terms=tuple(self.fridge_terms),
            excluded_recipe_uuids=tuple(self.excluded_recipe_uuids),
            excluded_ingredient_uuids=tuple(self.excluded_ingredient_uuids),
            excluded_groups=tuple(self.excluded_groups),
            recent_recipe_uuids=tuple(self.recent_recipe_uuids),
            max_reuse_per_recipe=self.max_reuse_per_recipe,
        )


class SlotProposalSchema(BaseModel):
    slot_date: date
    slot_code: SlotCode
    headcount: int
    suggestion: SuggestionSchema | None
    meal_item_payload: dict | None

    @classmethod
    def from_domain(cls, slot: SlotProposal) -> "SlotProposalSchema":
        suggestion = SuggestionSchema.from_domain(slot.suggestion) if slot.suggestion else None
        payload = None
        if slot.suggestion:
            payload = {
                "item_type": "recipe",
                "recipe_uuid": slot.suggestion.recipe_uuid,
            }
        return cls(
            slot_date=slot.slot_date,
            slot_code=slot.slot_code,
            headcount=slot.headcount,
            suggestion=suggestion,
            meal_item_payload=payload,
        )


class WeekProposalResponseSchema(BaseModel):
    date_start: date
    date_end: date
    coverage_rate: float
    slots: list[SlotProposalSchema]
    warnings: list[str]

    @classmethod
    def from_domain(cls, proposal: WeekProposal) -> "WeekProposalResponseSchema":
        return cls(
            date_start=proposal.date_start,
            date_end=proposal.date_end,
            coverage_rate=proposal.coverage_rate,
            slots=[SlotProposalSchema.from_domain(slot) for slot in proposal.slots],
            warnings=list(proposal.warnings),
        )


class IndicatorSlotSchema(BaseModel):
    slot_date: date
    slot_code: SlotCode
    headcount: int | None = Field(default=None, ge=0, le=50)
    recipes: list[CandidateRecipeSchema] = Field(default_factory=list)

    def to_domain(self) -> IndicatorSlot:
        return IndicatorSlot(
            slot_date=self.slot_date,
            slot_code=self.slot_code,
            headcount=self.headcount,
            recipes=tuple(recipe.to_domain() for recipe in self.recipes),
        )


class WeekIndicatorsRequestSchema(BaseModel):
    slots: list[IndicatorSlotSchema] = Field(default_factory=list)


class WeekIndicatorsResponseSchema(BaseModel):
    planned_slots_count: int
    recipe_count: int
    group_counts: dict[str, int]
    green_score_avg: float | None
    warnings: list[str]

    @classmethod
    def from_domain(cls, indicators: WeekIndicators) -> "WeekIndicatorsResponseSchema":
        return cls(
            planned_slots_count=indicators.planned_slots_count,
            recipe_count=indicators.recipe_count,
            group_counts=indicators.group_counts,
            green_score_avg=indicators.green_score_avg,
            warnings=list(indicators.warnings),
        )
