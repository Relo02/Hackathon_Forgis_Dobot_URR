import { getJson } from "./httpClient";
import type { RobotState } from "@/types";

export async function getRobotState(): Promise<RobotState> {
  return getJson<RobotState>("/robot/state");
}
