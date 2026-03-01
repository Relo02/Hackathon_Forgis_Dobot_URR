import type { RobotState } from "@/types";

interface RobotStatePanelProps {
  robotState: RobotState | null;
  error?: string | null;
}

function formatNumber(value: number, digits = 3): string {
  return value.toFixed(digits);
}

export function RobotStatePanel({ robotState, error }: RobotStatePanelProps) {
  const pose = robotState?.pose;
  const joints = robotState?.joints_deg ?? [];

  return (
    <div className="border-t border-border -mx-3 mt-3 px-3 pt-2.5 pb-3">
      <div className="flex items-center justify-between">
        <h2 className="forgis-text-label font-normal uppercase tracking-wider text-[var(--gunmetal-50)] font-forgis-digit">
          Coordinates
        </h2>
        <span className="forgis-text-detail font-forgis-digit text-[var(--gunmetal-50)]">
          {robotState?.connected ? "Live" : "Offline"}
        </span>
      </div>

      {error && (
        <div
          className="mt-2 rounded-md border px-2 py-1.5 forgis-text-detail font-forgis-body"
          style={{
            borderColor: "color-mix(in srgb, var(--status-critical) 30%, transparent)",
            background: "color-mix(in srgb, var(--status-critical) 8%, transparent)",
            color: "var(--status-critical)",
          }}
        >
          {error}
        </div>
      )}

      {!error && robotState?.last_error && (
        <div
          className="mt-2 rounded-md border px-2 py-1.5 forgis-text-detail font-forgis-body"
          style={{
            borderColor: "color-mix(in srgb, var(--status-critical) 30%, transparent)",
            background: "color-mix(in srgb, var(--status-critical) 8%, transparent)",
            color: "var(--status-critical)",
          }}
        >
          {robotState.last_error}
        </div>
      )}

      <div className="mt-2 space-y-2">
        <div>
          <div className="forgis-text-detail font-forgis-digit text-[var(--gunmetal-50)] uppercase">
            TCP
          </div>
          {pose ? (
            <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-1">
              {[
                ["x", pose.x],
                ["y", pose.y],
                ["z", pose.z],
                ["rx", pose.rx],
                ["ry", pose.ry],
                ["rz", pose.rz],
              ].map(([axis, value]) => (
                <div key={axis} className="flex items-center justify-between rounded bg-muted/40 px-2 py-1">
                  <span className="forgis-text-detail text-[var(--gunmetal-50)] font-forgis-digit uppercase">{axis}</span>
                  <span className="forgis-text-detail text-foreground font-forgis-body">{formatNumber(value as number)}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-1 rounded bg-muted/40 px-2 py-1.5 forgis-text-detail text-[var(--gunmetal-50)] font-forgis-body">
              Pose unavailable for this robot.
            </div>
          )}
        </div>

        <div>
          <div className="forgis-text-detail font-forgis-digit text-[var(--gunmetal-50)] uppercase">
            Joints
          </div>
          {joints.length > 0 ? (
            <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-1">
              {joints.map((joint, index) => (
                <div key={index} className="flex items-center justify-between rounded bg-muted/40 px-2 py-1">
                  <span className="forgis-text-detail text-[var(--gunmetal-50)] font-forgis-digit">J{index + 1}</span>
                  <span className="forgis-text-detail text-foreground font-forgis-body">{formatNumber(joint, 1)}°</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-1 rounded bg-muted/40 px-2 py-1.5 forgis-text-detail text-[var(--gunmetal-50)] font-forgis-body">
              Joint data unavailable.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
