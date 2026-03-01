import { useState } from "react";
import { TopBar } from "@/components/layout/Topbar";
import { CoderSidebar } from "@/components/chat/CoderSidebar";
import { FlowCanvas } from "@/components/flow/FlowCanvas";
import { CameraFeed } from "@/components/camera/CameraFeed";
import { DevicesSidebar } from "@/components/devices/DevicesSidebar";
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbSeparator,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import { useFlowGeneration } from "@/hooks/useFlowGeneration";
import { useCamera } from "@/hooks/useCamera";
import { useFlowExecution } from "@/hooks/useFlowExecution";
import { useRobotState } from "@/hooks/useRobotState";
import type { SelectedStep } from "@/types";

export function RobotControlPage() {
  const { flow, messages, loading, sendMessage, updateStepParams, addNode } = useFlowGeneration();
  const { cameraFrame, lastLabel, bboxOverlay, callbacks: cameraCallbacks } = useCamera();
  const { robotState, robotStateError } = useRobotState();
  const { flowStatus, nodeStates, finishing, errorLog, startFlow, pauseFlow, resumeFlow, finishFlow, resetFlow } = useFlowExecution(flow, cameraCallbacks);

  const [selectedStep, setSelectedStep] = useState<SelectedStep | null>(null);
  const [nodeCreatorOpen, setNodeCreatorOpen] = useState(false);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background">
      <TopBar />
      <div className="flex items-center px-4 py-1.5 border-b border-border bg-card/80 backdrop-blur-panel">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/" className="forgis-text-label font-forgis-body text-[var(--gunmetal-50)] no-underline">
                Forgis Factory
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbLink href="/" className="forgis-text-label font-forgis-body text-[var(--gunmetal-50)] no-underline">
                Line 1
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="forgis-text-label font-forgis-body text-[var(--gunmetal-50)]">
                Labelling and Sorting
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar - Devices (idle) or Camera Feed (active) */}
        {flowStatus === "idle" ? (
          <DevicesSidebar
            selectedStep={selectedStep}
            onDeselectStep={() => setSelectedStep(null)}
            onParamChange={(nodeId, stepId, key, value) => {
              updateStepParams(nodeId, stepId, {
                ...selectedStep?.step.params,
                [key]: value,
              });
              setSelectedStep((prev) =>
                prev
                  ? { ...prev, step: { ...prev.step, params: { ...prev.step.params, [key]: value } } }
                  : prev
              );
            }}
            nodeCreatorOpen={nodeCreatorOpen}
            onCloseNodeCreator={() => setNodeCreatorOpen(false)}
            onCreateNode={(creator) => {
              addNode(creator, robotState);
              setNodeCreatorOpen(false);
            }}
            robotState={robotState}
            robotStateError={robotStateError}
          />
        ) : (
          <CameraFeed frameUrl={cameraFrame} streaming lastLabel={lastLabel} bboxOverlay={bboxOverlay} />
        )}

        {/* Main content area - Flow canvas always visible */}
        <div className="flex flex-1 min-h-0 overflow-hidden p-5 bg-[var(--panel)]">
          <div className="flex-1 min-h-0 min-w-0">
            <FlowCanvas
              flow={flow}
              flowStatus={flowStatus}
              nodeStates={nodeStates}
              errorLog={errorLog}
              onStart={startFlow}
              onPause={pauseFlow}
              onResume={resumeFlow}
              onFinish={finishFlow}
              finishing={finishing}
              onReset={resetFlow}
              onSelectStep={(nodeId, step) => {
                setNodeCreatorOpen(false);
                setSelectedStep({ nodeId, step });
              }}
              onAddNode={() => {
                setSelectedStep(null);
                setNodeCreatorOpen(true);
              }}
            />
          </div>
        </div>

        {/* Right sidebar - Coder (hidden while flow is active) */}
        {flowStatus === "idle" && (
          <CoderSidebar messages={messages} loading={loading} onSend={sendMessage} />
        )}
      </div>
    </div>
  );
}
