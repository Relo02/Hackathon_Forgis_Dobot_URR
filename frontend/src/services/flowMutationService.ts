import type { Flow, FlowEdge, FlowNode, FlowStep, NodeCreatorState, RobotState } from "@/types";
import { layoutFlow } from "./flowLayoutService";

function getDefaultJointTargets(robotState?: RobotState | null): number[] {
  const liveJoints = robotState?.joints_deg;
  if (liveJoints && liveJoints.length > 0) {
    return liveJoints;
  }

  const jointCount =
    robotState?.joint_count ??
    (robotState?.robot_type === "panda" ? 7 : undefined) ??
    (robotState?.ip === "192.168.15.33" ? 7 : undefined) ??
    6;

  return Array.from({ length: jointCount }, () => 0);
}

function createDefaultStep(
  creator: NodeCreatorState,
  robotState?: RobotState | null,
): FlowStep[] {
  const stepSuffix = Date.now().toString().slice(-5);
  const baseId = creator.label.toLowerCase().replace(/\s+/g, "_");

  if (creator.nodeType !== "robot_action" || !creator.motionType) {
    return [];
  }

  if (creator.motionType === "joint") {
    const joints = getDefaultJointTargets(robotState);
    return [{
      id: `${baseId}_joint_${stepSuffix}`,
      skill: "move_joint",
      executor: "robot",
      params: {
        target_joints_deg: joints,
        acceleration: 0.2,
        velocity: 0.1,
        tolerance_deg: 1.0,
      },
      error_handling: {
        strategy: "stop",
        max_retries: 3,
        retry_delay_ms: 1000,
      },
      timeout_ms: 30000,
    }];
  }

  const pose = robotState?.pose;
  return [{
    id: `${baseId}_linear_${stepSuffix}`,
    skill: "move_linear",
    executor: "robot",
    params: {
      target_pose: pose
        ? [pose.x, pose.y, pose.z, pose.rx, pose.ry, pose.rz]
        : [0, 0, 0, 0, 0, 0],
      z_offset: 0,
      acceleration: 0.03,
      velocity: 0.02,
    },
    error_handling: {
      strategy: "stop",
      max_retries: 3,
      retry_delay_ms: 1000,
    },
    timeout_ms: 30000,
  }];
}

function createMotionNode(
  creator: NodeCreatorState,
  robotState?: RobotState | null,
): FlowNode {
  const nodeId = creator.label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "") || `node_${Date.now()}`;

  return {
    id: `${nodeId}_${Date.now().toString().slice(-4)}`,
    type: "state",
    label: creator.label.trim(),
    position: { x: 0, y: 0 },
    steps: createDefaultStep(creator, robotState),
  };
}

function createBaseFlow(node: FlowNode): Flow {
  return {
    id: `custom_flow_${Date.now()}`,
    name: "Custom Motion Flow",
    loop: false,
    variables: {},
    nodes: [
      { id: "start", type: "start", label: "Start", position: { x: 0, y: 0 } },
      node,
      { id: "end", type: "end", label: "End", position: { x: 0, y: 0 } },
    ],
    edges: [
      { id: `e_start_${node.id}`, source: "start", target: node.id },
      { id: `e_${node.id}_end`, source: node.id, target: "end" },
    ],
  };
}

function insertNodeBeforeEnd(flow: Flow, node: FlowNode): Flow {
  const edgesToEnd = flow.edges.filter((edge) => edge.target === "end");
  const stateNodes = flow.nodes.filter((candidate) => candidate.type === "state");
  const fallbackSources = stateNodes.length > 0 ? [stateNodes[stateNodes.length - 1].id] : [];
  const sourceIds = edgesToEnd.length > 0
    ? edgesToEnd.map((edge) => edge.source)
    : fallbackSources;

  const filteredEdges = flow.edges.filter((edge) => edge.target !== "end");
  const rewiredEdges: FlowEdge[] = sourceIds.map((sourceId, index) => ({
    id: `e_${sourceId}_${node.id}_${index}`,
    source: sourceId,
    target: node.id,
    data: { transitionType: "sequential" },
  }));

  return {
    ...flow,
    nodes: [...flow.nodes.filter((candidate) => candidate.id !== "end"), node, flow.nodes.find((candidate) => candidate.id === "end")!],
    edges: [
      ...filteredEdges,
      ...rewiredEdges,
      { id: `e_${node.id}_end`, source: node.id, target: "end" },
    ],
  };
}

export function addNodeToFlow(
  flow: Flow | null,
  creator: NodeCreatorState,
  robotState?: RobotState | null,
): Flow {
  const node = createMotionNode(creator, robotState);
  if (!flow) {
    return layoutFlow(createBaseFlow(node));
  }
  return layoutFlow(insertNodeBeforeEnd(flow, node));
}
