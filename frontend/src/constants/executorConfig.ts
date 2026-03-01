import { Bot, Cpu, Eye } from "lucide-react";
import type { NodeCreatorState } from "@/types";

// ── Executor icon mapping (used in flow nodes) ──────────────

export const EXECUTOR_ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  robot: Bot,
  camera: Eye,
  io_robot: Cpu,
};

// ── Node creator config ─────────────────────────────────────

export const NODE_TYPES = [
  { value: "robot_action", label: "Robot Action" },
  { value: "computer_vision", label: "Computer Vision" },
  { value: "sensors", label: "Sensors" },
] as const;

export const TASKS = [
  { value: "object_tracking", label: "Object Tracking" },
  { value: "classification", label: "Classification" },
  { value: "object_detection", label: "Object Detection" },
] as const;

export const MOTION_TYPES = [
  { value: "joint", label: "Joint Motion" },
  { value: "linear", label: "Linear Motion" },
  { value: "grasping", label: "Grasping" },
] as const;

export const EMPTY_CREATOR: NodeCreatorState = {
  nodeType: null,
  task: null,
  motionType: null,
  label: "",
};
