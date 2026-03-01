import { useEffect } from "react";
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  Background,
  BackgroundVariant,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Plus } from "lucide-react";
import { ContentPanel } from "@/components/layout/ContentPanel";
import { FlowControls } from "./FlowControls";
import { FlowAutoFit } from "./FlowAutoFit";
import { FlowAutoFollow } from "./FlowAutoFollow";
import { nodeTypes } from "./ExecutionNode";
import type {
  Flow as FlowType,
  FlowStep,
  FlowExecStatus,
  NodeExecState,
} from "@/types";
import {
  toReactFlowNodes,
  toReactFlowEdges,
  updateEdgeStyles,
  type ExecNode,
} from "@/services/flowTransformService";

interface FlowCanvasProps {
  flow: FlowType | null;
  flowStatus: FlowExecStatus;
  nodeStates: Record<string, NodeExecState>;
  errorLog?: string[];
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onFinish: () => void;
  finishing: boolean;
  onReset: () => void;
  onSelectStep?: (nodeId: string, step: FlowStep) => void;
  onAddNode?: () => void;
}

export function FlowCanvas({
  flow,
  flowStatus,
  nodeStates,
  errorLog,
  onStart,
  onPause,
  onResume,
  onFinish,
  finishing,
  onReset,
  onSelectStep,
  onAddNode,
}: FlowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<ExecNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Sync flow data → React Flow state (only when flow changes)
  useEffect(() => {
    if (!flow) {
      setNodes([
        {
          id: "welcome",
          type: "execution" as const,
          position: { x: 0, y: 0 },
          draggable: false,
          selectable: false,
          data: {
            label: "Welcome",
            nodeType: "default",
            nodeId: "welcome",
            message: "Generate a flow to get started.",
            execState: undefined,
            flowStatus: "idle" as const,
          },
        },
      ]);
      setEdges([]);
      return;
    }

    setNodes(toReactFlowNodes(flow, nodeStates, flowStatus, onSelectStep));
    setEdges(toReactFlowEdges(flow));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow]);

  // Update execution state on nodes + edge styling
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          execState: nodeStates[n.id],
          flowStatus,
        },
      })),
    );
    setEdges((eds) => updateEdgeStyles(eds, nodeStates, flowStatus));
  }, [nodeStates, flowStatus, setNodes, setEdges]);

  return (
    <ContentPanel
      title="Flow"
      className="h-full"
      contentClassName="p-0"
      scrollable={false}
      centerActions={
        flow ? (
          <FlowControls
            flowStatus={flowStatus}
            finishing={finishing}
            errorLog={errorLog}
            onStart={onStart}
            onPause={onPause}
            onResume={onResume}
            onFinish={onFinish}
            onReset={onReset}
          />
        ) : undefined
      }
      actions={
        (
          <button
            onClick={onAddNode}
            className="flex items-center justify-center w-7 h-7 rounded-md border border-border forgis-text-label font-normal text-foreground cursor-pointer hover:bg-muted/60 transition-colors"
            title="Add node"
          >
            <Plus size={14} />
          </button>
        )
      }
    >
      <div className="relative w-full h-full">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={{ type: "smoothstep" }}
          fitView
          fitViewOptions={{ padding: 0.3, maxZoom: 0.85 }}
          minZoom={0.2}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={16}
            size={1}
            color="var(--dot-grid-color)"
          />
          <FlowAutoFit flowId={flow?.id} />
          <FlowAutoFollow nodeStates={nodeStates} flowStatus={flowStatus} />
        </ReactFlow>
      </div>
    </ContentPanel>
  );
}
