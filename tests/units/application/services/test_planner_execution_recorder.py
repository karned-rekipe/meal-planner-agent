import pytest

from application.services.agent_run_service import AgentRunService
from application.services.planner_execution_recorder import PlannerExecutionRecorder


@pytest.fixture
def recorder(repo, logger):
    return PlannerExecutionRecorder(AgentRunService(repo, logger))


async def test_recorder_persists_successful_operation(recorder, repo):
    result = await recorder.execute(
        name="suggest_meal_plan_item",
        input_payload={"slot_code": "lunch"},
        transport="rest",
        operation=lambda: ("recipe-1",),
        serialize=list,
    )

    runs = await repo.find_all()
    assert result == ("recipe-1",)
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].input_payload == {"slot_code": "lunch"}
    assert runs[0].output_payload == ["recipe-1"]
    assert runs[0].duration_ms is not None


async def test_recorder_persists_failed_operation(recorder, repo):
    def fail() -> None:
        raise ValueError("invalid period")

    with pytest.raises(ValueError, match="invalid period"):
        await recorder.execute(
            name="propose_meal_plan_week",
            input_payload={},
            transport="mcp",
            operation=fail,
            serialize=lambda result: result,
        )

    runs = await repo.find_all()
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error == "invalid period"
