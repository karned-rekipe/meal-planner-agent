from dataclasses import dataclass, field
from datetime import date
from typing import Literal

SlotCode = Literal["lunch", "dinner"]


@dataclass(frozen=True, slots=True)
class CandidateRecipe:
    recipe_uuid: str
    title: str
    season_months: tuple[int, ...] = ()
    ingredient_uuids: tuple[str, ...] = ()
    ingredient_names: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    green_score: float | None = None


@dataclass(frozen=True, slots=True)
class SuggestionContext:
    slot_date: date
    slot_code: SlotCode
    headcount: int = 2
    candidates: tuple[CandidateRecipe, ...] = ()
    fridge_ingredient_uuids: tuple[str, ...] = ()
    fridge_terms: tuple[str, ...] = ()
    excluded_recipe_uuids: tuple[str, ...] = ()
    excluded_ingredient_uuids: tuple[str, ...] = ()
    excluded_groups: tuple[str, ...] = ()
    recent_recipe_uuids: tuple[str, ...] = ()
    max_suggestions: int = 3


@dataclass(frozen=True, slots=True)
class SuggestionResult:
    recipe_uuid: str
    title: str
    score: float
    reason_codes: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class WeekProposalContext:
    date_start: date
    date_end: date
    default_headcount: int = 2
    candidates: tuple[CandidateRecipe, ...] = ()
    fridge_ingredient_uuids: tuple[str, ...] = ()
    fridge_terms: tuple[str, ...] = ()
    excluded_recipe_uuids: tuple[str, ...] = ()
    excluded_ingredient_uuids: tuple[str, ...] = ()
    excluded_groups: tuple[str, ...] = ()
    recent_recipe_uuids: tuple[str, ...] = ()
    max_reuse_per_recipe: int = 1


@dataclass(frozen=True, slots=True)
class SlotProposal:
    slot_date: date
    slot_code: SlotCode
    headcount: int
    suggestion: SuggestionResult | None = None


@dataclass(frozen=True, slots=True)
class WeekProposal:
    date_start: date
    date_end: date
    slots: tuple[SlotProposal, ...]
    coverage_rate: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IndicatorSlot:
    slot_date: date
    slot_code: SlotCode
    recipes: tuple[CandidateRecipe, ...] = ()
    headcount: int | None = None


@dataclass(frozen=True, slots=True)
class WeekIndicators:
    planned_slots_count: int
    recipe_count: int
    group_counts: dict[str, int] = field(default_factory=dict)
    green_score_avg: float | None = None
    warnings: tuple[str, ...] = ()
