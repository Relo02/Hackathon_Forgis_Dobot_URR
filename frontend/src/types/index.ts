import type { ReactNode } from "react";

// ── Flow types (aligned with backend naming) ────────────────

export interface FlowStep {
  id: string;
  skill: string;
  executor: string;
  params?: Record<string, unknown>;
  store_result?: string | null;
  error_handling?: FlowErrorConfig;
  timeout_ms?: number;
}

export interface FlowErrorConfig {
  strategy: string;
  max_retries: number;
  retry_delay_ms: number;
  fallback_skill?: string | null;
}

export interface FlowNode {
  id: string;
  type: string;           // "state", "start", "end"
  label: string;          // display name
  steps?: FlowStep[];     // steps inside state nodes
  position: { x: number; y: number };
  style?: { width: number; height: number };
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  data?: Record<string, unknown>;
}

export interface Flow {
  id: string;
  name: string;
  loop?: boolean;
  variables?: Record<string, unknown>;
  nodes: FlowNode[];
  edges: FlowEdge[];
}

// ── Chat types ──────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

// ── Device types ────────────────────────────────────────────

export type DeviceType = "robot" | "camera" | "sensor";
export type DeviceStatus = "connected" | "warning" | "disconnected";

export interface Device {
  id: string;
  name: string;
  vendor: string;
  type: DeviceType;
  status: DeviceStatus;
  ip: string;
}

// ── Step selection (for parameter editor) ───────────────────

export interface SelectedStep {
  nodeId: string;
  step: FlowStep;
}

// ── Node creator (UI-only) ──────────────────────────────────

export interface NodeCreatorState {
  nodeType: string | null;
  task: string | null;
  motionType: "joint" | "linear" | null;
  label: string;
}

// ── Flow execution types ────────────────────────────────────

export type NodeExecStatus = "idle" | "running" | "success" | "failure";

export interface StepExecState {
  status: NodeExecStatus;
  retries?: number;
  error?: string;
  result?: Record<string, unknown>;
}

export interface NodeExecState {
  status: NodeExecStatus;
  durationMs?: number;
  error?: string;
  stepStates?: Record<string, StepExecState>; // Track individual step execution
  currentStep?: string; // Currently executing step ID
}

// Aligned with backend FlowExecutionStatus enum
export type FlowExecStatus = "idle" | "running" | "paused" | "completed" | "error";

// ── WebSocket messages: Server → Client (aligned with backend) ─────

export type ServerMessage =
  | { type: "connected"; message: string; timestamp: number }
  | { type: "flow_started"; flow_id: string; name: string; timestamp: number }
  | { type: "flow_completed"; flow_id: string; status: string; timestamp: number }
  | { type: "flow_paused"; flow_id: string; timestamp: number }
  | { type: "flow_resumed"; flow_id: string; timestamp: number }
  | { type: "flow_aborted"; flow_id: string; timestamp: number }
  | { type: "flow_error"; flow_id: string; error: string; step_id?: string; timestamp: number }
  | { type: "state_entered"; flow_id: string; state: string; timestamp: number }
  | { type: "state_completed"; flow_id: string; state: string; timestamp: number }
  | { type: "loop_restart"; flow_id: string; initial_state: string; timestamp: number }
  | { type: "step_started"; flow_id: string; step_id: string; skill: string; executor: string; timestamp: number }
  | { type: "step_completed"; flow_id: string; step_id: string; result: Record<string, unknown>; retries: number; timestamp: number }
  | { type: "step_error"; flow_id: string; step_id: string; error: string; strategy?: string; timestamp: number }
  | { type: "step_retry"; flow_id: string; step_id: string; attempt: number; max_retries: number; timestamp: number }
  | { type: "step_skipped"; flow_id: string; step_id: string; error: string; strategy: string; timestamp: number }
  | { type: "waiting_condition"; flow_id: string; state: string; timestamp: number }
  | { type: "camera_frame"; frame: string; width: number; height: number; timestamp: number }
  | { type: "bounding_box"; bbox: BoundingBox; frame_width: number; frame_height: number; display_duration_ms: number; timestamp: number }
  | { type: "pong" };

// ── Bounding box types ─────────────────────────────────────

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
  class_name: string;
}

export interface BoundingBoxOverlay {
  bbox: BoundingBox;
  frameWidth: number;
  frameHeight: number;
  expiresAt: number;
}

export interface RobotPose {
  x: number;
  y: number;
  z: number;
  rx: number;
  ry: number;
  rz: number;
}

export interface RobotState {
  timestamp: number;
  robot_type?: "ur" | "dobot" | "panda" | string;
  joint_count?: number;
  connected: boolean;
  ip?: string;
  joints_deg: number[] | null;
  pose?: RobotPose | null;
  moving?: boolean;
  last_error?: string | null;
}
/**
 * Props for the generic ContentPanel component
 */
export interface ContentPanelProps {
  /** Panel title displayed in the header */
  title: string;
  /** Optional subtitle displayed below the title */
  subtitle?: string;
  /** Optional action buttons/elements for the header (right side) */
  actions?: ReactNode;
  /** Optional center content for the header */
  centerActions?: ReactNode;
  /** Panel content */
  children?: ReactNode;
  /** Additional CSS classes for the outer card */
  className?: string;
  /** Additional CSS classes for the content area */
  contentClassName?: string;
  /** Enable scrolling in content area (default: true) */
  scrollable?: boolean;
}
