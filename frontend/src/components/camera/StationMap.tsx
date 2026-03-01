interface ZoneCardProps {
  zoneKey: string;
  zoneLabel: string;
  count: number;
  capacity: number;
}

interface MetricCardProps {
  metricKey: string;
  metricLabel: string;
  value: number;
}

export interface StationMetric {
  key: string;
  label: string;
  value: number;
}

function formatDecimal(value: number) {
  return value.toFixed(3);
}

function ZoneCard({ zoneKey, zoneLabel, count, capacity }: ZoneCardProps) {
  const pct = Math.min(count / capacity, 1);
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-[var(--platinum)] p-2">
      <span className="forgis-text-caption text-[var(--gunmetal-50)] font-forgis-digit leading-none">
        {zoneKey} ({zoneLabel})
      </span>
      <span
        className="forgis-text-label font-medium font-forgis-digit leading-none"
        style={{ color: pct >= 1 ? "var(--orange)" : "var(--gunmetal)" }}
      >
        {formatDecimal(count)}/{formatDecimal(capacity)}
      </span>
      <div className="h-[3px] w-full rounded-full bg-[var(--gunmetal-10)] mt-0.5">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct * 100}%`, background: pct >= 1 ? "var(--orange)" : "var(--accent-hover)" }}
        />
      </div>
    </div>
  );
}

function MetricCard({ metricKey, metricLabel, value }: MetricCardProps) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-[var(--platinum)] p-2">
      <span className="forgis-text-caption text-[var(--gunmetal-50)] font-forgis-digit leading-none">
        {metricKey}
      </span>
      <span className="forgis-text-caption text-[var(--gunmetal-50)] font-forgis-body leading-none">
        {metricLabel}
      </span>
      <span className="forgis-text-label font-medium font-forgis-digit leading-none text-[var(--gunmetal)]">
        {formatDecimal(value)}
      </span>
    </div>
  );
}

interface StationMapProps {
  zoneCounts: Record<string, number>;
  zoneLabels: Record<string, string>;
  containerCapacity: number;
  metrics?: StationMetric[];
}

export function StationMap({ zoneCounts, zoneLabels, containerCapacity, metrics }: StationMapProps) {
  if (metrics && metrics.length > 0) {
    return (
      <div className="flex flex-col flex-1 min-h-0 border-t border-border -mx-3 px-3 pt-3">
        <h2 className="forgis-text-label font-normal uppercase tracking-wider text-[var(--gunmetal-50)] font-forgis-digit mb-3">
          Station Map
        </h2>
        <div className="grid grid-cols-2 gap-2">
          {metrics.map((metric) => (
            <MetricCard
              key={metric.key}
              metricKey={metric.key}
              metricLabel={metric.label}
              value={metric.value}
            />
          ))}
        </div>
      </div>
    );
  }

  const total = zoneCounts.Zone_A + zoneCounts.Zone_B + zoneCounts.Zone_C;

  return (
    <div className="flex flex-col flex-1 min-h-0 border-t border-border -mx-3 px-3 pt-3">
      <h2 className="forgis-text-label font-normal uppercase tracking-wider text-[var(--gunmetal-50)] font-forgis-digit mb-3">
        Station Map
      </h2>

      {/* 2×2 grid: 3 containers (L-shape) + total (top-right) */}
      <div className="grid grid-cols-2 gap-2">
        {/* Top-left: Zone A */}
        <ZoneCard
          zoneKey="Zone A"
          zoneLabel={zoneLabels.Zone_A}
          count={zoneCounts.Zone_A}
          capacity={containerCapacity}
        />

        {/* Top-right: Total metric */}
        <div className="flex flex-col items-center justify-center p-2">
          <div className="flex items-baseline gap-0.5 leading-none">
            <span className="text-[1.5rem] font-medium font-forgis-digit text-[var(--gunmetal)]">
              {formatDecimal(total)}
            </span>
            <span className="forgis-text-caption font-forgis-digit text-[var(--gunmetal-50)]">
              /{formatDecimal(containerCapacity * 3)}
            </span>
          </div>
          <span className="forgis-text-caption text-[var(--gunmetal-50)] font-forgis-digit leading-none mt-1">
            Total
          </span>
        </div>

        {/* Bottom-left: Zone B */}
        <ZoneCard
          zoneKey="Zone B"
          zoneLabel={zoneLabels.Zone_B}
          count={zoneCounts.Zone_B}
          capacity={containerCapacity}
        />

        {/* Bottom-right: Zone C */}
        <ZoneCard
          zoneKey="Zone C"
          zoneLabel={zoneLabels.Zone_C}
          count={zoneCounts.Zone_C}
          capacity={containerCapacity}
        />
      </div>
    </div>
  );
}
