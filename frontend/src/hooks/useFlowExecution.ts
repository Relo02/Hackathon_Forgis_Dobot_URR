import { useCallback, useEffect, useRef, useState } from "react";
import {
  saveFlow as apiSaveFlow,
  startFlow as apiStartFlow,
  abortFlow as apiAbortFlow,
  pauseFlow as apiPauseFlow,
  resumeFlow as apiResumeFlow,
  finishFlow as apiFinishFlow,
} from "@/api/flowApi";
import { createFlowSocket } from "@/api/flowSocket";
import { startCameraStream, stopCameraStream } from "@/api/cameraApi";
import { findStateForStep } from "@/services/flowTransformService";
import type { CameraCallbacks } from "./useCamera";
import type {
  Flow,
  FlowExecStatus,
  NodeExecState,
  ServerMessage,
  StepExecState,
} from "@/types";

export function useFlowExecution(
  flow: Flow | null,
  camera: CameraCallbacks,
) {
  const [flowStatus, setFlowStatus] = useState<FlowExecStatus>("idle");
  const [nodeStates, setNodeStates] = useState<Record<string, NodeExecState>>({});
  const [finishing, setFinishing] = useState(false);
  const [errorLog, setErrorLog] = useState<string[]>([]);

  const socketRef = useRef<{ close: () => void } | null>(null);
  const handleMessageRef = useRef<(msg: ServerMessage) => void>(() => {});

  const appendError = useCallback((message: string) => {
    setErrorLog((prev) => {
      if (prev[prev.length - 1] === message) {
        return prev;
      }
      return [...prev.slice(-4), message];
    });
  }, []);

  const flowNeedsCamera = useCallback(
    (currentFlow: Flow | null) =>
      !!currentFlow?.nodes.some((node) =>
        node.steps?.some((step) => step.executor === "camera")
      ),
    []
  );

  // ── WebSocket Event Handling ────────────────────────────────

  const handleMessage = useCallback(
    (msg: ServerMessage) => {
      switch (msg.type) {
        case "connected":
          break;

        case "flow_started":
          setFlowStatus("running");
          break;

        case "flow_completed":
          setFlowStatus("completed");
          setFinishing(false);
          if (flowNeedsCamera(flow)) {
            void stopCameraStream().catch(() => undefined);
            camera.onStreamStop();
          }
          break;

        case "flow_aborted":
          setFlowStatus("idle");
          setFinishing(false);
          if (flowNeedsCamera(flow)) {
            void stopCameraStream().catch(() => undefined);
            camera.onStreamStop();
          }
          break;

        case "flow_paused":
          setFlowStatus("paused");
          break;

        case "flow_resumed":
          setFlowStatus("running");
          break;

        case "flow_error":
          setFlowStatus("error");
          setFinishing(false);
          if (flowNeedsCamera(flow)) {
            void stopCameraStream().catch(() => undefined);
            camera.onStreamStop();
          }
          appendError(msg.step_id ? `${msg.step_id}: ${msg.error}` : msg.error);
          break;

        case "loop_restart":
          if (flow) {
            const reset: Record<string, NodeExecState> = {};
            for (const node of flow.nodes) {
              reset[node.id] = { status: "idle", stepStates: {} };
            }
            setNodeStates(reset);
          }
          break;

        case "state_entered":
          setNodeStates((prev) => ({
            ...prev,
            [msg.state]: {
              ...prev[msg.state],
              status: "running",
            },
          }));
          break;

        case "state_completed":
          setNodeStates((prev) => ({
            ...prev,
            [msg.state]: {
              ...prev[msg.state],
              status: "success",
            },
          }));
          break;

        case "waiting_condition":
          break;

        case "step_started": {
          if (!flow) break;
          const stateId = findStateForStep(flow, msg.step_id);
          if (stateId) {
            setNodeStates((prev) => {
              const nodeState = prev[stateId] || { status: "running", stepStates: {} };
              const stepStates: Record<string, StepExecState> = {
                ...(nodeState.stepStates || {}),
                [msg.step_id]: { status: "running" },
              };
              return {
                ...prev,
                [stateId]: {
                  ...nodeState,
                  status: "running",
                  currentStep: msg.step_id,
                  stepStates,
                },
              };
            });
          }
          break;
        }

        case "step_completed": {
          // Capture label from get_label skill results
          if (msg.result?.label && typeof msg.result.label === "string") {
            camera.onLabel(msg.result.label);
          }

          if (!flow) break;
          const stateId = findStateForStep(flow, msg.step_id);
          if (stateId) {
            setNodeStates((prev) => {
              const nodeState = prev[stateId] || { status: "running", stepStates: {} };
              const stepStates: Record<string, StepExecState> = {
                ...(nodeState.stepStates || {}),
                [msg.step_id]: { status: "success", retries: msg.retries, result: msg.result },
              };
              return {
                ...prev,
                [stateId]: {
                  ...nodeState,
                  stepStates,
                },
              };
            });
          }
          break;
        }

        case "step_error": {
          appendError(`${msg.step_id}: ${msg.error}`);
          if (!flow) break;
          const stateId = findStateForStep(flow, msg.step_id);
          if (stateId) {
            setNodeStates((prev) => {
              const nodeState = prev[stateId] || { status: "running", stepStates: {} };
              const stepStates: Record<string, StepExecState> = {
                ...(nodeState.stepStates || {}),
                [msg.step_id]: { status: "failure", error: msg.error },
              };
              return {
                ...prev,
                [stateId]: {
                  ...nodeState,
                  status: "failure",
                  stepStates,
                },
              };
            });
          }
          break;
        }

        case "step_retry":
          break;

        case "step_skipped":
          break;

        case "camera_frame":
          camera.onFrame(msg.frame, msg.timestamp);
          break;

        case "bounding_box":
          camera.onBbox(msg.bbox, msg.frame_width, msg.frame_height, msg.display_duration_ms);
          break;
      }
    },
    [flow, camera, appendError]
  );

  // Keep ref updated with latest handleMessage to avoid stale closures in WebSocket
  useEffect(() => {
    handleMessageRef.current = handleMessage;
  }, [handleMessage]);

  // ── WebSocket connection ────────────────────────────────────

  const connectWebSocket = useCallback(async () => {
    if (socketRef.current) return;
    socketRef.current = await createFlowSocket(
      (msg) => handleMessageRef.current(msg),
      () => { socketRef.current = null; }
    );
  }, []);

  // ── Reset execution state when a new flow is generated ──────

  useEffect(() => {
    socketRef.current?.close();
    socketRef.current = null;

    if (flow) {
      const initial: Record<string, NodeExecState> = {};
      for (const node of flow.nodes) {
        initial[node.id] = { status: "idle", stepStates: {} };
      }
      setNodeStates(initial);
    } else {
      setNodeStates({});
    }
    setFlowStatus("idle");
    setErrorLog([]);
  }, [flow]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      socketRef.current?.close();
    };
  }, []);

  // ── Flow control functions ──────────────────────────────────

  const startFlow = useCallback(async () => {
    if (!flow) return;

    const initial: Record<string, NodeExecState> = {};
    for (const node of flow.nodes) {
      initial[node.id] = { status: "idle", stepStates: {} };
    }
    setNodeStates(initial);
    setFinishing(false);
    setErrorLog([]);

    try {
      await apiSaveFlow(flow);
      await connectWebSocket();

      const needsCamera = flowNeedsCamera(flow);
      if (needsCamera) {
        try {
          await startCameraStream(15);
        } catch (err) {
          appendError(
            `Camera stream unavailable: ${err instanceof Error ? err.message : "Unknown error"}`
          );
        }
      }

      await apiStartFlow(flow.id);
    } catch (err) {
      appendError(err instanceof Error ? err.message : "Failed to start flow");
      setFlowStatus("idle");
    }
  }, [flow, connectWebSocket, appendError, flowNeedsCamera]);

  const pauseFlow = useCallback(async () => {
    try {
      await apiPauseFlow();
    } catch (err) {
      appendError(err instanceof Error ? err.message : "Failed to pause flow");
    }
  }, [appendError]);

  const resumeFlow = useCallback(async () => {
    try {
      await apiResumeFlow();
    } catch (err) {
      appendError(err instanceof Error ? err.message : "Failed to resume flow");
    }
  }, [appendError]);

  const abortFlow = useCallback(async () => {
    try {
      await apiAbortFlow();
    } catch (err) {
      appendError(err instanceof Error ? err.message : "Failed to abort flow");
    }
    setFlowStatus("idle");
  }, [appendError]);

  const finishFlow = useCallback(async () => {
    setFinishing(true);
    try {
      await apiFinishFlow();
    } catch (err) {
      appendError(err instanceof Error ? err.message : "Failed to finish flow");
    }
  }, [appendError]);

  const resetFlow = useCallback(async () => {
    setFinishing(false);
    socketRef.current?.close();
    socketRef.current = null;

    if (flowNeedsCamera(flow)) {
      try {
        await stopCameraStream();
      } catch {
        // Ignore camera shutdown failures for non-camera motion testing.
      }
    }
    camera.onReset(); // clears frame, labels, QC, bbox

    if (flow) {
      const initial: Record<string, NodeExecState> = {};
      for (const node of flow.nodes) {
        initial[node.id] = { status: "idle", stepStates: {} };
      }
      setNodeStates(initial);
    }
    setFlowStatus("idle");
    setErrorLog([]);
  }, [flow, camera, flowNeedsCamera]);

  return {
    flowStatus,
    nodeStates,
    finishing,
    errorLog,
    startFlow,
    pauseFlow,
    resumeFlow,
    abortFlow,
    finishFlow,
    resetFlow,
  };
}
