import { useEffect, useState } from "react";
import { getRobotState } from "@/api/robotApi";
import type { RobotState } from "@/types";

export function useRobotState(pollMs = 1000) {
  const [robotState, setRobotState] = useState<RobotState | null>(null);
  const [robotStateError, setRobotStateError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const next = await getRobotState();
        if (!cancelled) {
          setRobotState(next);
          setRobotStateError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setRobotStateError(error instanceof Error ? error.message : "Failed to fetch robot state");
        }
      }
    };

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, pollMs);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [pollMs]);

  return { robotState, robotStateError };
}
