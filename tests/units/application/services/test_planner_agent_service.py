import json
from datetime import date
from pathlib import Path

import pytest

from application.services.planner_agent_service import PlannerAgentService
from domain.models.planner_agent import CandidateRecipe, SuggestionContext, WeekProposalContext


@pytest.fixture
def service() -> PlannerAgentService:
    return PlannerAgentService()


@pytest.fixture
def candidates() -> tuple[CandidateRecipe, ...]:
    return (
        CandidateRecipe(
            recipe_uuid="r-soupe",
            title="Soupe poireau carotte",
            season_months=(1, 2, 11, 12),
            ingredient_uuids=("i-poireau", "i-carotte"),
            ingredient_names=("poireau", "carotte"),
            groups=("legumes",),
            green_score=86,
        ),
        CandidateRecipe(
            recipe_uuid="r-ratatouille",
            title="Ratatouille courgette aubergine",
            season_months=(6, 7, 8, 9),
            ingredient_uuids=("i-courgette", "i-aubergine", "i-tomate"),
            ingredient_names=("courgette", "aubergine", "tomate"),
            groups=("legumes",),
            green_score=78,
        ),
        CandidateRecipe(
            recipe_uuid="r-bowl",
            title="Bowl lentille riz epinard",
            season_months=(2, 3, 4, 9, 10),
            ingredient_uuids=("i-lentille", "i-riz", "i-epinard"),
            ingredient_names=("lentille", "riz", "epinard"),
            groups=("legumineuses", "cereales"),
            green_score=72,
        ),
        CandidateRecipe(
            recipe_uuid="r-veloute",
            title="Veloute potimarron panais",
            season_months=(10, 11, 12, 1),
            ingredient_uuids=("i-potimarron", "i-panais"),
            ingredient_names=("potimarron", "panais"),
            groups=("legumes",),
            green_score=81,
        ),
    )


def test_suggest_item_prioritizes_fridge_and_season(service: PlannerAgentService, candidates: tuple[CandidateRecipe, ...]) -> None:
    suggestions = service.suggest_item(
        SuggestionContext(
            slot_date=date(2026, 1, 5),
            slot_code="lunch",
            candidates=candidates,
            fridge_terms=("poireau",),
            max_suggestions=2,
        )
    )

    assert suggestions[0].recipe_uuid == "r-soupe"
    assert "fridge_match" in suggestions[0].reason_codes
    assert "seasonal" in suggestions[0].reason_codes


def test_suggest_item_applies_exclusions(service: PlannerAgentService, candidates: tuple[CandidateRecipe, ...]) -> None:
    suggestions = service.suggest_item(
        SuggestionContext(
            slot_date=date(2026, 7, 5),
            slot_code="dinner",
            candidates=candidates,
            excluded_ingredient_uuids=("i-courgette",),
            max_suggestions=4,
        )
    )

    assert all(suggestion.recipe_uuid != "r-ratatouille" for suggestion in suggestions)


def test_propose_week_materializes_lunch_and_dinner(service: PlannerAgentService, candidates: tuple[CandidateRecipe, ...]) -> None:
    proposal = service.propose_week(
        WeekProposalContext(
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 7),
            candidates=candidates,
            max_reuse_per_recipe=4,
        )
    )

    assert len(proposal.slots) == 14
    assert proposal.coverage_rate > 0


def test_golden_scenarios_execute_without_error(service: PlannerAgentService, candidates: tuple[CandidateRecipe, ...]) -> None:
    path = Path(__file__).parents[3] / "golden" / "suggestion_scenarios.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"))

    assert len(scenarios) == 20
    for scenario in scenarios:
        suggestions = service.suggest_item(
            SuggestionContext(
                slot_date=date.fromisoformat(scenario["slot_date"]),
                slot_code=scenario["slot_code"],
                candidates=candidates,
                fridge_terms=tuple(scenario["fridge_terms"]),
                recent_recipe_uuids=tuple(scenario["recent_recipe_uuids"]),
                max_suggestions=3,
            )
        )
        assert suggestions
