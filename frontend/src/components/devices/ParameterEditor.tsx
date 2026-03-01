import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SelectedStep } from "@/types";

interface ParameterEditorProps {
  selectedStep: SelectedStep;
  onDeselectStep?: () => void;
  onParamChange?: (nodeId: string, stepId: string, key: string, value: unknown) => void;
}

export function ParameterEditor({ selectedStep, onDeselectStep, onParamChange }: ParameterEditorProps) {
  const isLinearRobotMove =
    selectedStep.step.skill === "move_linear" && selectedStep.step.executor === "robot";

  return (
    <div className="flex flex-col flex-1 min-h-0 border-t border-border -mx-3 mt-3">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-2.5 pb-1.5">
        <h2 className="forgis-text-label font-normal uppercase tracking-wider text-[var(--gunmetal-50)] font-forgis-digit">
          Parameters
        </h2>
        <button
          className="flex items-center justify-center w-5 h-5 rounded bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer border-none"
          onClick={onDeselectStep}
        >
          <X size={12} />
        </button>
      </div>

      {/* Skill info */}
      <div className="px-3 pb-2 space-y-0.5">
        <div className="forgis-text-detail font-normal text-foreground truncate font-forgis-digit">
          {selectedStep.step.skill}
        </div>
        <div className="forgis-text-detail text-[var(--gunmetal-50)] font-forgis-body">
          executor: {selectedStep.step.executor}
        </div>
        {isLinearRobotMove && (
          <div className="forgis-text-detail text-[var(--gunmetal-50)] font-forgis-body">
            Panda note: if live TCP pose is unavailable, `target_pose` is used as relative `[dx, dy, dz, rx, ry, rz]`.
          </div>
        )}
      </div>

      {/* Param fields */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {selectedStep.step.params && Object.keys(selectedStep.step.params).length > 0 ? (
          <div className="space-y-2.5">
            {Object.entries(selectedStep.step.params).map(([key, value]) => (
              <div key={`${selectedStep.step.id}-${key}`} className="flex flex-col gap-1">
                <label className="forgis-text-detail font-normal text-[var(--gunmetal-50)] font-forgis-digit">
                  {key}
                </label>
                {typeof value === "boolean" ? (
                  <Select
                    value={String(value)}
                    onValueChange={(v) =>
                      onParamChange?.(selectedStep.nodeId, selectedStep.step.id, key, v === "true")
                    }
                  >
                    <SelectTrigger className="h-7 forgis-text-detail text-[var(--gunmetal-50)]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">true</SelectItem>
                      <SelectItem value="false">false</SelectItem>
                    </SelectContent>
                  </Select>
                ) : typeof value === "number" ? (
                  <Input
                    type="number"
                    step="any"
                    className="h-7 forgis-text-detail text-[var(--gunmetal-50)]"
                    value={value}
                    onChange={(e) =>
                      onParamChange?.(
                        selectedStep.nodeId,
                        selectedStep.step.id,
                        key,
                        e.target.value === "" ? 0 : parseFloat(e.target.value),
                      )
                    }
                  />
                ) : Array.isArray(value) ? (
                  <div className="grid grid-cols-3 gap-1">
                    {(value as unknown[]).map((v, i) => (
                      <Input
                        key={i}
                        type="number"
                        step="any"
                        className="h-7 forgis-text-detail text-[var(--gunmetal-50)]"
                        value={typeof v === "number" ? v : String(v ?? "")}
                        onChange={(e) => {
                          const arr = [...(value as unknown[])];
                          arr[i] = e.target.value === "" ? 0 : parseFloat(e.target.value);
                          onParamChange?.(selectedStep.nodeId, selectedStep.step.id, key, arr);
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  <textarea
                    className="w-full px-3 py-1.5 bg-transparent border border-border rounded-md forgis-text-detail text-[var(--gunmetal-50)] font-forgis-body resize-none outline-none focus:border-ring"
                    style={{ fieldSizing: "content" } as React.CSSProperties}
                    value={String(value ?? "")}
                    rows={1}
                    onChange={(e) =>
                      onParamChange?.(selectedStep.nodeId, selectedStep.step.id, key, e.target.value)
                    }
                  />
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="forgis-text-detail text-[var(--gunmetal-50)] text-center py-4 font-forgis-body">
            No parameters for this step.
          </div>
        )}
      </div>
    </div>
  );
}
