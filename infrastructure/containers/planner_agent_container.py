from application.services.planner_agent_service import PlannerAgentService
from arclith import Arclith
from arclith.domain.ports.logger import Logger


def build_planner_agent_service(arclith: Arclith) -> tuple[PlannerAgentService, Logger]:
    return PlannerAgentService(), arclith.logger
