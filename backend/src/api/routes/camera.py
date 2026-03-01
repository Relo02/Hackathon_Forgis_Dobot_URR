"""REST endpoints for camera control."""

import asyncio
from typing import AsyncGenerator, Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/camera", tags=["camera"])

# CameraExecutor will be injected via app state
_camera_executor = None


def set_camera_executor(executor) -> None:
    """Set the camera executor instance (called during app initialization)."""
    global _camera_executor
    _camera_executor = executor


def get_executor():
    """Get the camera executor, raising if not initialized."""
    if _camera_executor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera executor not initialized",
        )
    return _camera_executor


# --- Request/Response Models ---


class StreamStartRequest(BaseModel):
    """Request to start streaming."""

    fps: int = Field(default=15, ge=1, le=30, description="Target FPS")


class StreamResponse(BaseModel):
    """Response for stream control operations."""

    success: bool
    streaming: bool
    message: Optional[str] = None


class CameraStateResponse(BaseModel):
    """Response for camera state."""

    connected: bool
    streaming: bool
    frame_size: Optional[dict] = None
    last_detection: Optional[dict] = None


# --- Endpoints ---


@router.post("/stream/start", response_model=StreamResponse)
async def start_stream(request: StreamStartRequest = StreamStartRequest()):
    """Start streaming camera frames over WebSocket."""
    executor = get_executor()

    if not executor.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera not connected",
        )

    started = await executor.start_streaming(fps=request.fps)

    return StreamResponse(
        success=True,
        streaming=True,
        message=f"Streaming started at {request.fps} FPS" if started else "Streaming already active",
    )


@router.post("/stream/stop", response_model=StreamResponse)
async def stop_stream():
    """Stop streaming camera frames."""
    executor = get_executor()

    stopped = await executor.stop_streaming()

    return StreamResponse(
        success=True,
        streaming=False,
        message="Streaming stopped" if stopped else "Streaming was not active",
    )


@router.get("/snapshot")
async def get_snapshot(quality: int = 90):
    """
    Get a single JPEG snapshot from the camera.

    Args:
        quality: JPEG quality (1-100).

    Returns:
        JPEG image data.
    """
    executor = get_executor()

    if not executor.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera not connected",
        )

    jpeg_data = executor.get_snapshot_jpeg(quality=min(100, max(1, quality)))

    if jpeg_data is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No frame available",
        )

    return Response(
        content=jpeg_data,
        media_type="image/jpeg",
        headers={"Content-Disposition": "inline; filename=snapshot.jpg"},
    )


@router.get("/state", response_model=CameraStateResponse)
async def get_camera_state():
    """Get current camera state."""
    executor = get_executor()
    return executor.get_state_summary()


# Gear class set (treat all variants as one category)
_GEAR_CLASSES = {"gear1", "gear2", "gear3", "gear4", "gear5"}


def _is_valid_gear_box(x1: int, y1: int, x2: int, y2: int, frame_w: int, frame_h: int) -> bool:
    """
    Reject obvious false positives using geometry:
      - box area must be 2%–50% of the frame (tiny clips and full-frame boxes are noise)
      - aspect ratio must be between 0.3 and 3.0 (gears are roughly circular)
    """
    bw, bh = x2 - x1, y2 - y1
    if bw <= 0 or bh <= 0:
        return False
    area_frac = (bw * bh) / (frame_w * frame_h)
    if area_frac < 0.02 or area_frac > 0.50:
        return False
    aspect = bw / bh
    if aspect < 0.3 or aspect > 3.0:
        return False
    return True


async def _detection_frame_generator(
    executor, conf: float, fps: int
) -> AsyncGenerator[bytes, None]:
    """Yield MJPEG boundary frames with YOLO detections drawn."""
    # Load model in thread pool so we don't block the event loop on cold start
    loop = asyncio.get_event_loop()
    model = await loop.run_in_executor(None, executor._get_yolo_model)
    interval = 1.0 / fps
    colour_gear = (56, 255, 56)   # green
    colour_other = (255, 200, 0)  # cyan-ish

    while True:
        t_start = asyncio.get_event_loop().time()

        frame = executor._camera.get_latest_frame()
        if frame is None:
            await asyncio.sleep(interval)
            continue

        # Run YOLO in thread pool so we don't block the event loop
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, lambda: model(frame.copy(), verbose=False, conf=conf)
        )

        out = frame.copy()
        h, w = out.shape[:2]

        any_gear = False
        for result in results:
            for box in result.boxes:
                cls_name = model.names[int(box.cls)]
                if cls_name not in _GEAR_CLASSES:
                    continue
                box_conf = float(box.conf)
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                if not _is_valid_gear_box(x1, y1, x2, y2, w, h):
                    continue
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                any_gear = True

                cv2.rectangle(out, (x1, y1), (x2, y2), colour_gear, 2)
                cv2.drawMarker(out, (cx, cy), colour_gear, cv2.MARKER_CROSS, 18, 2)

                label = f"{cls_name}  {box_conf:.0%}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                cv2.rectangle(out, (x1, y1 - th - 8), (x1 + tw + 6, y1), colour_gear, cv2.FILLED)
                cv2.putText(out, label, (x1 + 3, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        status_text = "GEAR DETECTED" if any_gear else "NO GEAR"
        status_colour = (56, 255, 56) if any_gear else (56, 56, 255)
        cv2.rectangle(out, (0, 0), (w, 28), (30, 30, 30), cv2.FILLED)
        cv2.putText(out, status_text, (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_colour, 2, cv2.LINE_AA)
        cv2.putText(out, f"conf>={conf:.2f}  {fps}fps", (w - 160, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA)

        _, jpeg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 75])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg.tobytes()
            + b"\r\n"
        )

        elapsed = asyncio.get_event_loop().time() - t_start
        await asyncio.sleep(max(0.0, interval - elapsed))


@router.get("/stream/raw")
async def raw_stream(
    fps: int = Query(default=15, ge=1, le=30, description="Target FPS"),
):
    """
    Plain MJPEG stream — no detection overlay.
    Open directly in a browser: http://localhost:8000/api/camera/stream/raw
    """
    executor = get_executor()

    if not executor.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera not connected",
        )

    async def _raw_generator():
        interval = 1.0 / fps
        while True:
            t_start = asyncio.get_event_loop().time()
            jpeg = executor._camera.get_frame_jpeg(quality=80)
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
            elapsed = asyncio.get_event_loop().time() - t_start
            await asyncio.sleep(max(0.0, interval - elapsed))

    return StreamingResponse(
        _raw_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/stream/detection")
async def detection_stream(
    conf: float = Query(default=0.03, ge=0.001, le=1.0, description="Confidence threshold"),
    fps: int = Query(default=10, ge=1, le=30, description="Target FPS"),
):
    """
    MJPEG stream with live YOLO detections overlaid.
    Open directly in a browser: http://localhost:8000/api/camera/stream/detection
    """
    executor = get_executor()

    if not executor.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera not connected",
        )

    return StreamingResponse(
        _detection_frame_generator(executor, conf=conf, fps=fps),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
