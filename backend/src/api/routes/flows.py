"""REST endpoints for flow management."""

import json
import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

from google import genai
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from flow import FlowSchema, FlowStatusResponse

router = APIRouter(prefix="/api/flows", tags=["flows"])

# FlowManager will be injected via app state
_flow_manager = None


def set_flow_manager(manager) -> None:
    """Set the flow manager instance (called during app initialization)."""
    global _flow_manager
    _flow_manager = manager


def get_manager():
    """Get the flow manager, raising if not initialized."""
    if _flow_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flow manager not initialized",
        )
    return _flow_manager


# --- Request/Response Models ---


class FlowListResponse(BaseModel):
    """Response for listing flows."""

    flows: list[str]


class FlowCreateResponse(BaseModel):
    """Response for creating/updating a flow."""

    success: bool
    message: str
    flow_id: Optional[str] = None


class FlowStartResponse(BaseModel):
    """Response for starting a flow."""

    success: bool
    message: str


class FlowAbortResponse(BaseModel):
    """Response for aborting a flow."""

    success: bool
    message: str


class FlowGenerateRequest(BaseModel):
    """Request for generating a flow from prompt."""

    prompt: str


class FlowStep(BaseModel):
    """Step within a state (aligned with backend naming)."""

    id: str
    skill: str
    executor: str
    params: Optional[dict[str, Any]] = None
    store_result: Optional[str] = None
    error_handling: Optional[dict[str, Any]] = None
    timeout_ms: Optional[int] = None


class FlowNode(BaseModel):
    """Node in the frontend flow format (aligned with backend naming)."""

    id: str
    type: str  # "state", "start", "end"
    label: str
    steps: Optional[list[FlowStep]] = None  # For state nodes
    position: dict[str, float]
    style: Optional[dict[str, Any]] = None  # For sizing


class FlowEdge(BaseModel):
    """Edge in the frontend flow format."""

    id: str
    source: str
    target: str
    type: str = "transitionEdge"
    data: Optional[dict[str, Any]] = None


class FlowGenerateResponse(BaseModel):
    """Response with frontend-compatible flow format."""

    id: str
    name: str
    loop: bool = False
    variables: dict[str, Any] = Field(default_factory=dict)
    nodes: list[FlowNode]
    edges: list[FlowEdge]


def convert_backend_to_frontend(flow: FlowSchema) -> FlowGenerateResponse:
    """
    Convert backend flow format to frontend node/edge format.

    Backend: states with steps, transitions between states
    Frontend: start node, state nodes (containing steps), end node, edges

    Uses actual transitions from the flow definition.
    """
    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []

    # Positions are set to (0,0) — the frontend's layoutFlow() computes real positions.

    # Add start node
    start_node_id = "start"
    nodes.append(FlowNode(
        id=start_node_id,
        type="start",
        label="Start",
        position={"x": 0, "y": 0},
    ))

    # Convert each state to a node with steps inside
    for state in flow.states:
        node_id = state.name

        steps = [
            FlowStep(
                id=step.id,
                skill=step.skill,
                executor=step.executor,
                params=step.params,
                store_result=step.store_result,
                error_handling=step.error_handling.model_dump(),
                timeout_ms=step.timeout_ms,
            )
            for step in state.steps
        ]

        nodes.append(FlowNode(
            id=node_id,
            type="state",
            label=state.name,
            steps=steps,
            position={"x": 0, "y": 0},
        ))

    # Add end node
    end_node_id = "end"
    nodes.append(FlowNode(
        id=end_node_id,
        type="end",
        label="End",
        position={"x": 0, "y": 0},
    ))

    # Edge from start to initial state
    edges.append(FlowEdge(
        id=f"e_{start_node_id}_{flow.initial_state}",
        source=start_node_id,
        target=flow.initial_state,
    ))

    # Convert actual transitions to edges
    for i, t in enumerate(flow.transitions):
        edge_data: dict[str, Any] = {"transitionType": t.type}
        if t.condition:
            edge_data["condition"] = t.condition

        edges.append(FlowEdge(
            id=f"e_{t.from_state}_{t.to_state}_{i}",
            source=t.from_state,
            target=t.to_state,
            data=edge_data,
        ))

    # Find terminal states (no outgoing transitions)
    states_with_outgoing = {t.from_state for t in flow.transitions}
    terminal_states = [s.name for s in flow.states if s.name not in states_with_outgoing]

    # Add loop-back and/or end edges for terminal states
    for state_name in terminal_states:
        if flow.loop:
            edges.append(FlowEdge(
                id=f"e_loop_{state_name}_{flow.initial_state}",
                source=state_name,
                target=flow.initial_state,
                data={"isLoop": True},
            ))
        edges.append(FlowEdge(
            id=f"e_{state_name}_{end_node_id}",
            source=state_name,
            target=end_node_id,
        ))

    return FlowGenerateResponse(
        id=flow.id,
        name=flow.name,
        loop=flow.loop,
        variables=flow.variables,
        nodes=nodes,
        edges=edges,
    )


# --- Endpoints ---


@router.get("", response_model=FlowListResponse)
async def list_flows():
    """List all available flows."""
    manager = get_manager()
    return FlowListResponse(flows=manager.list_flows())


@router.get("/status", response_model=FlowStatusResponse)
async def get_status():
    """Get current execution status."""
    manager = get_manager()
    return manager.get_status()


@router.get("/{flow_id}", response_model=FlowSchema)
async def get_flow(flow_id: str):
    """Get a flow definition by ID."""
    manager = get_manager()
    flow = manager.get_flow(flow_id)
    if flow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow '{flow_id}' not found",
        )
    return flow


@router.post("", response_model=FlowCreateResponse)
async def create_flow(flow: FlowSchema):
    """Create or update a flow."""
    manager = get_manager()
    success, error = manager.save_flow(flow)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Failed to save flow",
        )
    return FlowCreateResponse(
        success=True,
        message=f"Flow '{flow.id}' saved",
        flow_id=flow.id,
    )


@router.delete("/{flow_id}")
async def delete_flow(flow_id: str):
    """Delete a flow."""
    manager = get_manager()
    if not manager.delete_flow(flow_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow '{flow_id}' not found",
        )
    return {"success": True, "message": f"Flow '{flow_id}' deleted"}


@router.post("/{flow_id}/start", response_model=FlowStartResponse)
async def start_flow(flow_id: str):
    """Start executing a flow."""
    manager = get_manager()
    success, message = await manager.start_flow(flow_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT
            if "already running" in message.lower()
            else status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return FlowStartResponse(success=True, message=message)


@router.post("/abort", response_model=FlowAbortResponse)
async def abort_flow():
    """Abort the currently running flow."""
    manager = get_manager()
    success, message = await manager.abort_flow()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return FlowAbortResponse(success=True, message=message)


class FlowFinishResponse(BaseModel):
    """Response for finishing a flow."""

    success: bool
    message: str


class FlowPauseResponse(BaseModel):
    """Response for pausing a flow."""

    success: bool
    message: str


class FlowResumeResponse(BaseModel):
    """Response for resuming a flow."""

    success: bool
    message: str


@router.post("/finish", response_model=FlowFinishResponse)
async def finish_flow():
    """Request graceful finish — complete current loop cycle then stop."""
    manager = get_manager()
    success, message = await manager.finish_flow()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return FlowFinishResponse(success=True, message=message)


@router.post("/pause", response_model=FlowPauseResponse)
async def pause_flow():
    """Pause the currently running flow."""
    manager = get_manager()
    success, message = await manager.pause_flow()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return FlowPauseResponse(success=True, message=message)


@router.post("/resume", response_model=FlowResumeResponse)
async def resume_flow():
    """Resume a paused flow."""
    manager = get_manager()
    success, message = await manager.resume_flow()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return FlowResumeResponse(success=True, message=message)


_GEMINI_MODEL = "gemini-3-flash-preview"

_FLOW_SYSTEM_PROMPT_TEMPLATE = """\
You are a robot flow generator. Given a natural-language task description, produce a JSON object that conforms EXACTLY to the FlowSchema below. Return ONLY raw JSON — no markdown fences, no explanation.

## FlowSchema
{
  "id": "<snake_case_id>",
  "name": "<Human Readable Name>",
  "initial_state": "<name of first state>",
  "loop": false,
  "variables": {},
  "states": [
    {
      "name": "<unique_state_name>",
      "steps": [
        {
          "id": "<unique_step_id>",
          "skill": "<skill_name>",
          "executor": "<executor_type>",
          "params": { ... },
          "timeout_ms": 30000
        }
      ]
    }
  ],
  "transitions": [
    { "type": "sequential", "from_state": "<state_a>", "to_state": "<state_b>" }
  ]
}

## Available Skills

Robot executor ("executor": "robot"):
- move_joint: params {"target_joints_deg": [j1, j2, ..., j__JOINT_COUNT__]} — exactly __JOINT_COUNT__ joint angles in degrees for the current robot
- move_linear: params {"target_pose": [x, y, z, rx, ry, rz]} — Cartesian pose (metres + radians)
- grasp: params {"width": w, "speed": s, "force": f} — grasp an object at width w (metres)
- release: params {"speed": s} — open the gripper to release the current object

Camera executor ("executor": "camera"):
- get_label: params {"prompt": "<what to read>", "use_bbox": false}
- get_bounding_box: params {"prompt": "<what to detect>"}
- start_streaming: params {}
- stop_streaming: params {}

## Rules
- Every state referenced in transitions must exist in the states array.
- initial_state must match the name of the first state.
- Use sequential transitions for linear flows. Use conditional transitions (type "conditional", add "condition" field) only when the prompt implies branching.
- Use placeholder joint values [__JOINT_PLACEHOLDER__] when exact positions are unknown — the user will fill them in.
- Step ids must be unique across the entire flow.
- Keep flows concise: only add states that the prompt requires.
"""


def _get_expected_joint_count() -> int:
    """Return the joint count for the configured robot type."""
    robot_type = os.environ.get("ROBOT_TYPE", "panda").lower()
    return 7 if robot_type == "panda" else 6


def _build_flow_system_prompt() -> str:
    """Build the Gemini system prompt with the active robot joint count."""
    joint_count = _get_expected_joint_count()
    joint_placeholder = ",".join(["0"] * joint_count)
    return (
        _FLOW_SYSTEM_PROMPT_TEMPLATE
        .replace("__JOINT_COUNT__", str(joint_count))
        .replace("__JOINT_PLACEHOLDER__", joint_placeholder)
    )


def _normalize_generated_flow(flow_dict: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM-generated joint targets to the current robot's joint count."""
    expected_joint_count = _get_expected_joint_count()

    for state in flow_dict.get("states", []):
        if not isinstance(state, dict):
            continue
        for step in state.get("steps", []):
            if not isinstance(step, dict) or step.get("skill") != "move_joint":
                continue

            params = step.get("params")
            if not isinstance(params, dict):
                continue

            target_joints = params.get("target_joints_deg")
            if not isinstance(target_joints, list):
                continue

            normalized_joints = list(target_joints[:expected_joint_count])
            if len(normalized_joints) < expected_joint_count:
                normalized_joints.extend([0] * (expected_joint_count - len(normalized_joints)))
            params["target_joints_deg"] = normalized_joints

    return flow_dict


def _get_gemini_client() -> genai.Client:
    """Create a Gemini client from the API key env var."""
    # Try loading .env if python-dotenv is available (for non-Docker runs)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set in environment or .env")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEMINI_API_KEY environment variable is not set",
        )
    print(f"[DEBUG] GEMINI_API_KEY loaded (first 8 chars): {api_key[:8]}...")
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> str:
    """Strip optional markdown fences from LLM output."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


@router.post("/generate", response_model=FlowGenerateResponse)
async def generate_flow(request: FlowGenerateRequest):
    """Generate a flow from a natural-language prompt using Gemini."""
    logger.info("generate_flow called with prompt: %r", request.prompt)

    client = _get_gemini_client()

    try:
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=request.prompt,
            config={"system_instruction": _build_flow_system_prompt()},
        )
        raw_text = response.text
        print("Gemini raw response:", raw_text)
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc}",
        )

    try:
        flow_dict = _normalize_generated_flow(json.loads(_extract_json(raw_text)))
        flow = FlowSchema(**flow_dict)
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Failed to parse Gemini response: %s\nRaw: %s", exc, raw_text)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse generated flow: {exc}",
        )

    valid, error = flow.validate_flow()
    if not valid:
        logger.error("Generated flow failed validation: %s", error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Generated flow is invalid: {error}",
        )

    return convert_backend_to_frontend(flow)
