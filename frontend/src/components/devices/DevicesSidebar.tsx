import { useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import type { Device, NodeCreatorState, RobotState, SelectedStep } from "@/types";
import { DEFAULT_DEVICES } from "@/constants/deviceConfig";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DeviceList } from "./DeviceList";
import { AddDeviceDialog } from "./AddDeviceDialog";
import { NodeCreatorDialog } from "./NodeCreatorDialog";
import { ParameterEditor } from "./ParameterEditor";
import { RobotStatePanel } from "./RobotStatePanel";

interface DevicesSidebarProps {
  selectedStep?: SelectedStep | null;
  onDeselectStep?: () => void;
  onParamChange?: (nodeId: string, stepId: string, key: string, value: unknown) => void;
  nodeCreatorOpen?: boolean;
  onCloseNodeCreator?: () => void;
  onCreateNode?: (creator: NodeCreatorState) => void;
  robotState?: RobotState | null;
  robotStateError?: string | null;
}

export function DevicesSidebar({
  selectedStep,
  onDeselectStep,
  onParamChange,
  nodeCreatorOpen,
  onCloseNodeCreator,
  onCreateNode,
  robotState,
  robotStateError,
}: DevicesSidebarProps) {
  const [devices, setDevices] = useState<Device[]>(DEFAULT_DEVICES);
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={cn(
        "relative flex flex-col bg-card border-r border-border transition-[width] duration-250 ease-in-out overflow-hidden",
        collapsed ? "w-9" : "w-64"
      )}
    >
      {/* Toggle */}
      <button
        className="absolute top-2 right-1 z-10 flex items-center justify-center w-7 h-7 rounded bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer border-none"
        onClick={() => setCollapsed((c) => !c)}
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>

      {!collapsed && (
        <div className="flex flex-col pt-10 px-3 pb-0 overflow-hidden h-full">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <h2 className="forgis-text-title font-normal uppercase text-[var(--gunmetal-50)] leading-none font-forgis-digit">
              Devices
            </h2>
            <AddDeviceDialog
              trigger={
                <Button variant="outline" size="sm" className="h-6 gap-1 px-1.5 forgis-text-detail">
                  <Plus className="w-3 h-3" />
                  Add
                </Button>
              }
              onAdd={(device) => setDevices((prev) => [...prev, device])}
            />
          </div>

          {/* Device list */}
          <div className={cn("overflow-y-auto -mx-3", selectedStep ? "shrink-0 max-h-[32%]" : "shrink-0 max-h-[28%]")}>
            <DeviceList devices={devices} compact />
          </div>

          <RobotStatePanel robotState={robotState ?? null} error={robotStateError} />

          {/* Node creator dialog */}
          <NodeCreatorDialog
            open={!!nodeCreatorOpen}
            onClose={() => onCloseNodeCreator?.()}
            onAdd={onCreateNode}
          />

          {/* Parameter editor (inline) */}
          {selectedStep && (
            <ParameterEditor
              selectedStep={selectedStep}
              onDeselectStep={onDeselectStep}
              onParamChange={onParamChange}
            />
          )}
        </div>
      )}
    </div>
  );
}
