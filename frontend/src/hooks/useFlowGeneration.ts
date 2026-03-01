import { useCallback, useState } from "react";
import { generateFlow } from "@/api/flowApi";
import { addNodeToFlow } from "@/services/flowMutationService";
import { layoutFlow } from "@/services/flowLayoutService";
import type { ChatMessage, Flow, NodeCreatorState, RobotState } from "@/types";

export function useFlowGeneration() {
  const [flow, setFlow] = useState<Flow | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const sendMessage = useCallback(async (content: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const result = await generateFlow(content);
      setFlow(layoutFlow(result));

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Flow generated with ${result.nodes.length} nodes and ${result.edges.length} edges.`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateStepParams = useCallback(
    (nodeId: string, stepId: string, params: Record<string, unknown>) => {
      setFlow((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          nodes: prev.nodes.map((node) =>
            node.id === nodeId
              ? {
                  ...node,
                  steps: node.steps?.map((s) =>
                    s.id === stepId ? { ...s, params } : s
                  ),
                }
              : node
          ),
        };
      });
    },
    []
  );

  const addNode = useCallback((creator: NodeCreatorState, robotState?: RobotState | null) => {
    setFlow((prev) => addNodeToFlow(prev, creator, robotState));
  }, []);

  return { flow, messages, loading, sendMessage, updateStepParams, addNode };
}
