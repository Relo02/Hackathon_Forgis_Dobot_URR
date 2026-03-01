import type { Flow, FlowEdge, FlowStep } from "@/types";

type BackendStep = FlowStep & {
  executor: "robot" | "camera" | "io_robot" | "hand";
  params: Record<string, unknown>;
};

type BackendFlow = {
  id: string;
  name: string;
  initial_state: string;
  loop: boolean;
  variables: Record<string, unknown>;
  states: Array<{
    name: string;
    steps: BackendStep[];
  }>;
  transitions: Array<{
    type: "sequential" | "conditional";
    from_state: string;
    to_state: string;
    condition?: string;
  }>;
};

type BackendTransition = BackendFlow["transitions"][number];

function isStateEdge(edge: FlowEdge): boolean {
  return edge.source !== "start" && edge.target !== "end" && edge.data?.isLoop !== true;
}

function toBackendTransition(edge: FlowEdge): BackendTransition {
  const transitionType: BackendTransition["type"] =
    edge.data?.transitionType === "conditional" ? "conditional" : "sequential";

  const transition: BackendTransition = {
    type: transitionType,
    from_state: edge.source,
    to_state: edge.target,
  };

  if (typeof edge.data?.condition === "string") {
    transition.condition = edge.data.condition;
  }

  return transition;
}

export function toBackendFlow(flow: Flow): BackendFlow {
  const startEdge = flow.edges.find((edge) => edge.source === "start");
  if (!startEdge) {
    throw new Error("Flow is missing a start transition");
  }

  const states = flow.nodes
    .filter((node) => node.type === "state")
    .map((node) => ({
      name: node.id,
      steps: (node.steps ?? []).map((step) => ({
        ...step,
        executor: step.executor as BackendStep["executor"],
        params: (step.params ?? {}) as Record<string, unknown>,
      })),
    }));

  const transitions: BackendFlow["transitions"] = flow.edges.filter(isStateEdge).map(toBackendTransition);

  return {
    id: flow.id,
    name: flow.name,
    initial_state: startEdge.target,
    loop: flow.loop ?? false,
    variables: flow.variables ?? {},
    states,
    transitions,
  };
}
