from adapters.input.fastapi.routers import AdminRouter, AgentRunRouter, PlannerAgentRouter
from arclith import Arclith
from fastapi import FastAPI
from infrastructure.containers.agent_run_container import build_agent_run_service
from infrastructure.containers.planner_agent_container import build_planner_agent_service
from infrastructure.purge_registry import purge_registry


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    service, logger = build_agent_run_service(arclith)
    planner_agent_service, planner_agent_logger = build_planner_agent_service(arclith)
    purge_registry.register("agent_runs", service.purge)
    app.include_router(AgentRunRouter(service, logger).router)
    app.include_router(PlannerAgentRouter(planner_agent_service, planner_agent_logger).router)
    app.include_router(AdminRouter(purge_registry).router)
