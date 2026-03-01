import { Play, Pause, Flag, RotateCcw, Loader2 } from "lucide-react";
import type { FlowExecStatus } from "@/types";

interface FlowControlsProps {
  flowStatus: FlowExecStatus;
  finishing: boolean;
  errorLog?: string[];
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onFinish: () => void;
  onReset: () => void;
}

export function FlowControls({
  flowStatus,
  finishing,
  errorLog = [],
  onStart,
  onPause,
  onResume,
  onFinish,
  onReset,
}: FlowControlsProps) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-2">
        {flowStatus === "idle" && (
          <button
            onClick={onStart}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-white forgis-text-label font-normal font-forgis-digit cursor-pointer border-none hover:bg-[var(--accent-hover)]"
          >
            <Play size={12} /> Run
          </button>
        )}

        {flowStatus === "running" && (
          <>
            <button
              onClick={onPause}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted text-foreground forgis-text-label font-normal font-forgis-digit cursor-pointer border-none hover:bg-muted/70"
            >
              <Pause size={12} /> Pause
            </button>
            {finishing ? (
              <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted text-muted-foreground forgis-text-label font-normal font-forgis-digit">
                <Loader2 size={12} className="animate-spin" /> Finishing…
              </span>
            ) : (
              <button
                onClick={onFinish}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted text-foreground forgis-text-label font-normal font-forgis-digit cursor-pointer border-none hover:bg-muted/70"
              >
                <Flag size={12} /> Finish
              </button>
            )}
          </>
        )}

        {flowStatus === "paused" && (
          <>
            <button
              onClick={onResume}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-white forgis-text-label font-normal font-forgis-digit cursor-pointer border-none hover:bg-[var(--accent-hover)]"
            >
              <Play size={12} /> Resume
            </button>
            {finishing ? (
              <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted text-muted-foreground forgis-text-label font-normal font-forgis-digit">
                <Loader2 size={12} className="animate-spin" /> Finishing…
              </span>
            ) : (
              <button
                onClick={onFinish}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted text-foreground forgis-text-label font-normal font-forgis-digit cursor-pointer border-none hover:bg-muted/70"
              >
                <Flag size={12} /> Finish
              </button>
            )}
          </>
        )}

        {(flowStatus === "completed" || flowStatus === "error") && (
          <>
            <button
              onClick={onReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted text-foreground forgis-text-label font-normal font-forgis-digit cursor-pointer border-none hover:bg-muted/70"
            >
              <RotateCcw size={12} /> Reset
            </button>
            <button
              onClick={onStart}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-white forgis-text-label font-normal font-forgis-digit cursor-pointer border-none hover:bg-[var(--accent-hover)] whitespace-nowrap"
            >
              <Play size={12} /> {flowStatus === "error" ? "Try Again" : "Re-run"}
            </button>
          </>
        )}

        {flowStatus !== "idle" && (
          <span className="forgis-text-detail text-muted-foreground uppercase tracking-wider ml-2 font-forgis-digit">
            {flowStatus}
          </span>
        )}
      </div>

      {errorLog.length > 0 && (
        <div
          className="w-[420px] max-w-full rounded-md border px-3 py-2"
          style={{
            borderColor: "color-mix(in srgb, var(--status-critical) 30%, transparent)",
            background: "color-mix(in srgb, var(--status-critical) 8%, transparent)",
          }}
        >
          <div className="forgis-text-detail font-forgis-digit uppercase" style={{ color: "var(--status-critical)" }}>
            Execution Log
          </div>
          <div className="mt-1 space-y-1">
            {errorLog.slice(-3).map((entry, index) => (
              <div key={`${index}-${entry}`} className="forgis-text-detail font-forgis-body" style={{ color: "var(--status-critical)" }}>
                {entry}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
