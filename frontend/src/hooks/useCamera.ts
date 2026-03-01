import { useMemo, useRef, useState } from "react";
import type { BoundingBox, BoundingBoxOverlay } from "@/types";

export interface CameraCallbacks {
  onFrame: (frame: string, timestamp: number) => void;
  onBbox: (bbox: BoundingBox, frameWidth: number, frameHeight: number, durationMs: number) => void;
  onLabel: (label: string) => void;
  onGrasp: () => void;
  /** Called on flow_completed / aborted / error — clears the live frame only. */
  onStreamStop: () => void;
  /** Called on resetFlow — clears all camera state (frame, labels, bbox). */
  onReset: () => void;
}

export function useCamera() {
  const [cameraFrame, setCameraFrame] = useState<string | null>(null);
  const [lastLabel, setLastLabel] = useState<{ label: string; version: number } | null>(null);
  const [lastGrasp, setLastGrasp] = useState<{ version: number } | null>(null);
  const [bboxOverlay, setBboxOverlay] = useState<BoundingBoxOverlay | null>(null);

  const lastFrameTimestampRef = useRef(0);
  const labelVersionRef = useRef(0);
  const graspVersionRef = useRef(0);
  const bboxTimerRef = useRef<number | null>(null);

  const callbacks: CameraCallbacks = useMemo(() => ({
    onFrame: (frame: string, timestamp: number) => {
      if (timestamp > lastFrameTimestampRef.current) {
        lastFrameTimestampRef.current = timestamp;
        setCameraFrame(`data:image/jpeg;base64,${frame}`);
      }
    },

    onBbox: (bbox: BoundingBox, frameWidth: number, frameHeight: number, durationMs: number) => {
      if (bboxTimerRef.current) {
        window.clearTimeout(bboxTimerRef.current);
      }

      setBboxOverlay({
        bbox,
        frameWidth,
        frameHeight,
        expiresAt: Date.now() + durationMs,
      });

      bboxTimerRef.current = window.setTimeout(() => {
        setBboxOverlay(null);
        bboxTimerRef.current = null;
      }, durationMs);
    },

    onLabel: (label: string) => {
      labelVersionRef.current += 1;
      setLastLabel({ label, version: labelVersionRef.current });
    },

    onGrasp: () => {
      graspVersionRef.current += 1;
      setLastGrasp({ version: graspVersionRef.current });
    },

    onStreamStop: () => {
      setCameraFrame(null);
    },

    onReset: () => {
      setCameraFrame(null);
      setLastLabel(null);
      setLastGrasp(null);
      if (bboxTimerRef.current) {
        window.clearTimeout(bboxTimerRef.current);
        bboxTimerRef.current = null;
      }
      setBboxOverlay(null);
      lastFrameTimestampRef.current = 0;
      labelVersionRef.current = 0;
      graspVersionRef.current = 0;
    },
  }), []);

  return { cameraFrame, lastLabel, lastGrasp, bboxOverlay, callbacks };
}
