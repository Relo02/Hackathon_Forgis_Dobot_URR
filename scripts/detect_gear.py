"""
Gear detection: answers two questions:
  1. Is there a gear in the image?
  2. Where is it? (pixel center + bounding box)

Run:
    docker exec forgis-backend bash -c \
        "source /app/.venv/bin/activate && python3 /tmp/detect_gear.py"

Env vars:
    CONF_THRESHOLD  minimum confidence (default: 0.2)
    OUTPUT_PATH     annotated image output (default: /tmp/gear_result.jpg)
    SNAPSHOT_URL    camera API endpoint
"""

import os
import urllib.request

import cv2
import numpy as np
from ultralytics import YOLO

MODEL_PATH     = "/app/weights/gears.pt"
SNAPSHOT_URL   = os.environ.get("SNAPSHOT_URL",  "http://localhost:8000/api/camera/snapshot")
OUTPUT_PATH    = os.environ.get("OUTPUT_PATH",   "/tmp/gear_result.jpg")
CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", "0.03"))

# All gear classes from the dataset — treated as one "gear" category
GEAR_CLASSES = {"gear1", "gear2", "gear3", "gear4", "gear5"}


def _is_valid_gear_box(x1, y1, x2, y2, frame_w, frame_h) -> bool:
    """Reject false positives: too small, too large, or wrong aspect ratio."""
    bw, bh = x2 - x1, y2 - y1
    if bw <= 0 or bh <= 0:
        return False
    area_frac = (bw * bh) / (frame_w * frame_h)
    if area_frac < 0.02 or area_frac > 0.50:
        return False
    aspect = bw / bh
    return 0.3 <= aspect <= 3.0


def fetch_snapshot() -> np.ndarray:
    with urllib.request.urlopen(SNAPSHOT_URL, timeout=10) as r:
        data = r.read()
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("Failed to decode snapshot")
    return frame


def detect_gear(frame: np.ndarray, model: YOLO) -> dict:
    """
    Returns:
        {
            "gear_found": bool,
            "confidence": float,       # best detection confidence
            "class": str,              # gear type (gear1 … gear5)
            "center_px": (cx, cy),    # pixel centre of best detection
            "bbox_px": (x1,y1,x2,y2) # pixel bounding box
        }
    """
    h, w = frame.shape[:2]
    results = model(frame, verbose=False)

    best = None
    for result in results:
        for box in result.boxes:
            cls_name = model.names[int(box.cls)]
            conf     = float(box.conf)
            if cls_name not in GEAR_CLASSES or conf < CONF_THRESHOLD:
                continue
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            if not _is_valid_gear_box(x1, y1, x2, y2, w, h):
                continue
            if best is None or conf > best["confidence"]:
                best = {
                    "gear_found":  True,
                    "confidence":  conf,
                    "class":       cls_name,
                    "center_px":   ((x1 + x2) // 2, (y1 + y2) // 2),
                    "bbox_px":     (x1, y1, x2, y2),
                }

    if best is None:
        return {"gear_found": False, "confidence": 0.0,
                "class": None, "center_px": None, "bbox_px": None}
    return best


def annotate(frame: np.ndarray, result: dict) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]

    if result["gear_found"]:
        x1, y1, x2, y2 = result["bbox_px"]
        cx, cy = result["center_px"]
        colour = (56, 255, 56)  # green

        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
        cv2.drawMarker(out, (cx, cy), colour, cv2.MARKER_CROSS, 18, 2)

        label = f"{result['class']}  {result['confidence']:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(out, (x1, y1 - th - 8), (x1 + tw + 6, y1), colour, cv2.FILLED)
        cv2.putText(out, label, (x1 + 3, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

        coord = f"center: ({cx}, {cy})"
        cv2.putText(out, coord, (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1, cv2.LINE_AA)

        status_text = f"GEAR DETECTED  conf={result['confidence']:.0%}"
        status_colour = (56, 255, 56)
    else:
        status_text  = "NO GEAR DETECTED"
        status_colour = (56, 56, 255)  # red

    cv2.rectangle(out, (0, 0), (w, 30), (30, 30, 30), cv2.FILLED)
    cv2.putText(out, status_text, (8, 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_colour, 2, cv2.LINE_AA)
    return out


def main():
    print(f"[model] loading {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    print(f"[model] classes: {list(model.names.values())}")

    print(f"[camera] fetching snapshot ...")
    frame = fetch_snapshot()
    print(f"[camera] {frame.shape[1]}x{frame.shape[0]}")

    result = detect_gear(frame, model)

    print("\n── Result ─────────────────────────────────")
    if result["gear_found"]:
        cx, cy = result["center_px"]
        x1, y1, x2, y2 = result["bbox_px"]
        print(f"  GEAR FOUND")
        print(f"  class      : {result['class']}")
        print(f"  confidence : {result['confidence']:.1%}")
        print(f"  center     : pixel ({cx}, {cy})")
        print(f"  bbox       : [{x1}, {y1}, {x2}, {y2}]")
    else:
        print("  NO GEAR IN FRAME")
    print("───────────────────────────────────────────\n")

    annotated = annotate(frame, result)
    cv2.imwrite(OUTPUT_PATH, annotated)
    print(f"[output] saved → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
