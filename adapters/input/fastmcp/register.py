"""MCP tools registration."""

import fastmcp
from adapters.input.fastmcp.tools import AdminMCP, AgentRunMCP, PlannerAgentMCP
from arclith import Arclith
from infrastructure.containers.agent_run_container import build_agent_run_service
from infrastructure.containers.planner_agent_container import build_planner_agent_service
from application.services.planner_execution_recorder import PlannerExecutionRecorder
from infrastructure.purge_registry import purge_registry


def register_tools(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    """Register all MCP tools."""
    service, logger = build_agent_run_service(arclith)
    planner_agent_service, planner_agent_logger = build_planner_agent_service(arclith)
    purge_registry.register("agent_runs", service.purge)
    AgentRunMCP(service, logger, mcp)
    PlannerAgentMCP(planner_agent_service, planner_agent_logger, mcp, PlannerExecutionRecorder(service))
    AdminMCP(purge_registry, logger, mcp)
