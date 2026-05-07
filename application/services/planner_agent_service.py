from collections import Counter
from datetime import date, timedelta

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

MAX_PLAN_DAYS = 31
SLOT_CODES = ("lunch", "dinner")


class PlannerAgentService:
    """Deterministic V3 meal-planner agent core.

    This service is intentionally side-effect free. LLM orchestration can wrap it later, while
    golden scenarios can already exercise stable business rules.
    """

    def suggest_item(self, context: SuggestionContext) -> tuple[SuggestionResult, ...]:
        scored = [
            self._score_candidate(candidate, context)
            for candidate in context.candidates
            if not self._is_excluded(candidate, context)
        ]
        scored = [suggestion for suggestion in scored if suggestion.score > 0]
        scored.sort(key=lambda suggestion: (-suggestion.score, suggestion.title.lower()))
        return tuple(scored[: context.max_suggestions])

    def propose_week(self, context: WeekProposalContext) -> WeekProposal:
        days = tuple(self._date_range(context.date_start, context.date_end))
        recent = set(context.recent_recipe_uuids)
        selected_counts: Counter[str] = Counter()
        slots: list[SlotProposal] = []
        warnings: list[str] = []

        for day in days:
            for slot_code in SLOT_CODES:
                slot_context = SuggestionContext(
                    slot_date=day,
                    slot_code=slot_code,
                    headcount=context.default_headcount,
                    candidates=context.candidates,
                    fridge_ingredient_uuids=context.fridge_ingredient_uuids,
                    fridge_terms=context.fridge_terms,
                    excluded_recipe_uuids=context.excluded_recipe_uuids,
                    excluded_ingredient_uuids=context.excluded_ingredient_uuids,
                    excluded_groups=context.excluded_groups,
                    recent_recipe_uuids=tuple(recent),
                    max_suggestions=max(len(context.candidates), 1),
                )
                suggestions = [
                    suggestion
                    for suggestion in self.suggest_item(slot_context)
                    if selected_counts[suggestion.recipe_uuid] < context.max_reuse_per_recipe
                ]
                suggestion = suggestions[0] if suggestions else None
                if suggestion is None:
                    warnings.append(f"no_candidate:{day.isoformat()}:{slot_code}")
                else:
                    selected_counts[suggestion.recipe_uuid] += 1
                    recent.add(suggestion.recipe_uuid)
                slots.append(
                    SlotProposal(
                        slot_date=day,
                        slot_code=slot_code,
                        headcount=context.default_headcount,
                        suggestion=suggestion,
                    )
                )

        coverage = 0.0 if not slots else sum(1 for slot in slots if slot.suggestion is not None) / len(slots)
        return WeekProposal(
            date_start=context.date_start,
            date_end=context.date_end,
            slots=tuple(slots),
            coverage_rate=round(coverage, 4),
            warnings=tuple(warnings),
        )

    def compute_indicators(self, slots: tuple[IndicatorSlot, ...]) -> WeekIndicators:
        group_counts: Counter[str] = Counter()
        green_scores: list[float] = []
        recipe_count = 0

        for slot in slots:
            for recipe in slot.recipes:
                recipe_count += 1
                for group in recipe.groups:
                    group_counts[group] += 1
                if recipe.green_score is not None:
                    green_scores.append(recipe.green_score)

        warnings: list[str] = []
        if recipe_count == 0:
            warnings.append("no_recipe")
        if not group_counts and recipe_count > 0:
            warnings.append("missing_groups")

        green_score_avg = None
        if green_scores:
            green_score_avg = round(sum(green_scores) / len(green_scores), 2)

        return WeekIndicators(
            planned_slots_count=len(slots),
            recipe_count=recipe_count,
            group_counts=dict(sorted(group_counts.items())),
            green_score_avg=green_score_avg,
            warnings=tuple(warnings),
        )

    def _score_candidate(self, candidate: CandidateRecipe, context: SuggestionContext) -> SuggestionResult:
        score = 50.0
        reason_codes: list[str] = []

        season_score = self._season_score(candidate, context.slot_date.month)
        score += season_score
        if season_score > 0:
            reason_codes.append("seasonal")
        elif candidate.season_months:
            reason_codes.append("out_of_season")

        fridge_score = self._fridge_score(candidate, context)
        score += fridge_score
        if fridge_score > 0:
            reason_codes.append("fridge_match")

        if candidate.green_score is not None:
            score += min(max(candidate.green_score, 0), 100) / 5
            reason_codes.append("green_score")

        if candidate.recipe_uuid in context.recent_recipe_uuids:
            score -= 35
            reason_codes.append("recent_penalty")
        else:
            reason_codes.append("anti_repetition")

        score = round(max(score, 0), 2)
        return SuggestionResult(
            recipe_uuid=candidate.recipe_uuid,
            title=candidate.title,
            score=score,
            reason_codes=tuple(reason_codes),
            reason=self._build_reason(reason_codes),
        )

    @staticmethod
    def _date_range(date_start: date, date_end: date) -> list[date]:
        if date_end < date_start:
            raise ValueError("date_end must be greater than or equal to date_start")
        days_count = (date_end - date_start).days + 1
        if days_count > MAX_PLAN_DAYS:
            raise ValueError(f"week proposal period cannot exceed {MAX_PLAN_DAYS} days")
        return [date_start + timedelta(days=offset) for offset in range(days_count)]

    @staticmethod
    def _season_score(candidate: CandidateRecipe, month: int) -> float:
        if not candidate.season_months:
            return 8.0
        return 32.0 if month in candidate.season_months else -18.0

    @staticmethod
    def _fridge_score(candidate: CandidateRecipe, context: SuggestionContext) -> float:
        candidate_uuids = set(candidate.ingredient_uuids)
        fridge_uuids = set(context.fridge_ingredient_uuids)
        uuid_matches = len(candidate_uuids & fridge_uuids)

        terms = {term.strip().lower() for term in context.fridge_terms if term.strip()}
        searchable = " ".join((candidate.title, *candidate.ingredient_names)).lower()
        text_matches = sum(1 for term in terms if term in searchable)

        return min((uuid_matches + text_matches) * 15.0, 45.0)

    @staticmethod
    def _is_excluded(candidate: CandidateRecipe, context: SuggestionContext) -> bool:
        if candidate.recipe_uuid in context.excluded_recipe_uuids:
            return True
        if set(candidate.ingredient_uuids) & set(context.excluded_ingredient_uuids):
            return True
        return bool(set(candidate.groups) & set(context.excluded_groups))

    @staticmethod
    def _build_reason(reason_codes: list[str]) -> str:
        labels = {
            "seasonal": "recette alignée avec la saison",
            "out_of_season": "saisonnalité défavorable",
            "fridge_match": "utilise des ingrédients disponibles",
            "green_score": "score environnemental pris en compte",
            "recent_penalty": "pénalisée car déjà vue récemment",
            "anti_repetition": "non utilisée récemment",
        }
        return ", ".join(labels[code] for code in reason_codes if code in labels)
