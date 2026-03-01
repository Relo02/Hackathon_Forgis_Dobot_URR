import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Video } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BoundingBoxOverlay } from "@/types";
import { CONTAINER_CAPACITY, ZONE_LABELS_V2 } from "@/constants/cameraConfig";
import { BboxOverlay } from "./BboxOverlay";
import { DetectionStatus, type LatestDetection } from "./DetectionStatus";
import { StationMap, type StationMetric } from "./StationMap";

interface CameraFeedProps {
  frameUrl: string | null;
  streaming: boolean;
  lastLabel?: { label: string; version: number } | null;
  lastGrasp?: { version: number } | null;
  bboxOverlay?: BoundingBoxOverlay | null;
  commitCountsOnGrasp?: boolean;
  graspMetrics?: StationMetric[];
}

export function CameraFeed({
  frameUrl,
  streaming,
  lastLabel,
  lastGrasp,
  bboxOverlay,
  commitCountsOnGrasp = false,
  graspMetrics,
}: CameraFeedProps) {
  const zoneLabels = ZONE_LABELS_V2;
  const [collapsed, setCollapsed] = useState(false);
  const [latestDetection, setLatestDetection] = useState<LatestDetection | null>(null);
  const lastBboxRef = useRef<string | null>(null);
  const pendingZoneRef = useRef<string | null>(null);
  const shotCounterRef = useRef(0);
  const [zoneCounts, setZoneCounts] = useState<Record<string, number>>({
    Zone_A: 0, Zone_B: 0, Zone_C: 0,
  });

  // Track latest label and stage it for the station map.
  useEffect(() => {
    if (lastLabel) {
      shotCounterRef.current += 1;
      setLatestDetection({ type: "label", label: zoneLabels[lastLabel.label] ?? lastLabel.label, shot: shotCounterRef.current });
      if (lastLabel.label in zoneLabels) {
        pendingZoneRef.current = lastLabel.label;
        if (!commitCountsOnGrasp) {
          setZoneCounts((prev) => ({ ...prev, [lastLabel.label]: prev[lastLabel.label] + 1 }));
          pendingZoneRef.current = null;
        }
      }
    }
  }, [commitCountsOnGrasp, lastLabel, zoneLabels]);

  // Commit the pending classified item only after a successful grasp.
  useEffect(() => {
    if (!commitCountsOnGrasp || !lastGrasp || !pendingZoneRef.current) {
      return;
    }

    const zoneKey = pendingZoneRef.current;
    setZoneCounts((prev) => ({ ...prev, [zoneKey]: prev[zoneKey] + 1 }));
    pendingZoneRef.current = null;
  }, [commitCountsOnGrasp, lastGrasp]);

  // Track latest bbox detection
  useEffect(() => {
    if (bboxOverlay) {
      const bboxKey = `${bboxOverlay.bbox.class_name}-${bboxOverlay.bbox.confidence.toFixed(2)}`;
      if (lastBboxRef.current !== bboxKey) {
        lastBboxRef.current = bboxKey;
        shotCounterRef.current += 1;
        setLatestDetection({
          type: "bbox",
          label: bboxOverlay.bbox.class_name,
          confidence: bboxOverlay.bbox.confidence,
          shot: shotCounterRef.current,
        });
      }
    }
  }, [bboxOverlay]);

const imgRef = useRef<HTMLImageElement>(null);
  const [imgRect, setImgRect] = useState<{ width: number; height: number; left: number; top: number } | null>(null);

  // Update image rect on load and resize
  useEffect(() => {
    const updateRect = () => {
      if (imgRef.current) {
        const rect = imgRef.current.getBoundingClientRect();
        const parent = imgRef.current.parentElement?.getBoundingClientRect();
        if (parent) {
          setImgRect({
            width: rect.width,
            height: rect.height,
            left: rect.left - parent.left,
            top: rect.top - parent.top,
          });
        }
      }
    };

    updateRect();
    window.addEventListener("resize", updateRect);
    return () => window.removeEventListener("resize", updateRect);
  }, [frameUrl]);

  // Calculate bbox overlay position scaled to displayed image
  const getBboxStyle = () => {
    if (!bboxOverlay || !imgRect) return null;

    const scaleX = imgRect.width / bboxOverlay.frameWidth;
    const scaleY = imgRect.height / bboxOverlay.frameHeight;

    return {
      left: imgRect.left + bboxOverlay.bbox.x * scaleX,
      top: imgRect.top + bboxOverlay.bbox.y * scaleY,
      width: bboxOverlay.bbox.width * scaleX,
      height: bboxOverlay.bbox.height * scaleY,
    };
  };

  const bboxStyle = getBboxStyle();

  return (
    <div
      className={cn(
        "relative flex flex-col bg-card border-r border-border transition-[width] duration-250 ease-in-out overflow-hidden",
        collapsed ? "w-9" : "w-96",
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
          {/* ── Camera Feed Section ──────────────────────── */}
          <div className="flex items-center justify-between mb-3">
            <h2 className="forgis-text-label font-normal uppercase tracking-wider text-[var(--gunmetal-50)] font-forgis-digit">
              Camera Feed
            </h2>
            <Video size={12} className="text-[var(--gunmetal-50)]" />
          </div>

          {/* Subtitle */}
          <span className="forgis-text-detail text-[var(--gunmetal-50)] leading-none mb-4 font-forgis-body">
            Real time acquisition from robot camera
          </span>

          {/* Image container */}
          <div className="relative bg-[var(--platinum)] rounded-[8px] aspect-video overflow-hidden shrink-0">
            {streaming && frameUrl ? (
              <>
                <img
                  ref={imgRef}
                  src={frameUrl}
                  alt="Camera stream"
                  className="absolute inset-0 w-full h-full object-cover"
                  onLoad={() => {
                    if (imgRef.current) {
                      const rect = imgRef.current.getBoundingClientRect();
                      const parent = imgRef.current.parentElement?.getBoundingClientRect();
                      if (parent) {
                        setImgRect({
                          width: rect.width,
                          height: rect.height,
                          left: rect.left - parent.left,
                          top: rect.top - parent.top,
                        });
                      }
                    }
                  }}
                />
                {bboxStyle && bboxOverlay && (
                  <BboxOverlay bboxStyle={bboxStyle} overlay={bboxOverlay} />
                )}
              </>
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-[var(--gunmetal-50)] forgis-text-reading font-forgis-body">
                  Waiting for stream...
                </span>
              </div>
            )}
          </div>

          <DetectionStatus latestDetection={latestDetection} />

          <StationMap
            zoneCounts={zoneCounts}
            zoneLabels={zoneLabels}
            containerCapacity={CONTAINER_CAPACITY}
            metrics={graspMetrics}
          />
        </div>
      )}
    </div>
  );
}
