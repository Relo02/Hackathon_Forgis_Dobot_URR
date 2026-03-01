import { Activity, Bot, Eye } from "lucide-react";
import type { DeviceType, DeviceStatus, Device } from "@/types";

// ── Icon mapping ─────────────────────────────────────────────

export const DEVICE_ICONS: Record<DeviceType, React.ComponentType<{ className?: string }>> = {
  robot: Bot,
  camera: Eye,
  sensor: Activity,
};

// ── Status display ───────────────────────────────────────────

export const STATUS_COLOR: Record<DeviceStatus, string> = {
  connected: "var(--status-healthy)",
  warning: "var(--orange)",
  disconnected: "var(--status-critical)",
};

export const STATUS_LABEL: Record<DeviceStatus, string> = {
  connected: "Connected",
  warning: "Warning",
  disconnected: "Offline",
};

// ── Vendor brands per device type ────────────────────────────

export const BRANDS: Record<DeviceType, string[]> = {
  robot: ["Franka", "Universal Robots", "ABB", "KUKA", "Fanuc", "Yaskawa", "Doosan"],
  camera: ["Intel RealSense", "Cognex", "Keyence", "Basler", "Sick", "Allied Vision"],
  sensor: ["Sick", "Pepperl+Fuchs", "Banner Engineering", "ifm", "Balluff"],
};

export const PANDA_DEFAULT_IP = "192.168.15.33";

// ── Default devices (pre-populated) ─────────────────────────

export const DEFAULT_DEVICES: Device[] = [
  {
    id: "robot-default",
    name: "UR3",
    vendor: "Universal Robots",
    type: "robot",
    status: "disconnected",
    ip: "192.168.0.101",
  },
  {
    id: "cam-default",
    name: "RealSense D435",
    vendor: "Intel",
    type: "camera",
    status: "disconnected",
    ip: "localhost:8765",
  },
];

// ── Add-device form state ────────────────────────────────────

export interface DeviceFormData {
  type: DeviceType | "";
  brand: string;
  robotModel: string;
  name: string;
  apiEndpoint: string;
}

export const EMPTY_FORM: DeviceFormData = {
  type: "",
  brand: "",
  robotModel: "",
  name: "",
  apiEndpoint: "",
};
