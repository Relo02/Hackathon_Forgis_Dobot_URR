#!/usr/bin/env python3
"""Minimal ROS 2 Panda linear motion test.

This script exercises the same Panda ROS node + executor path used by the
backend, but without FastAPI, flows, camera, or WebSocket layers.

Behavior:
- starts ``PandaNode`` inside an ``rclpy`` executor
- waits for the Panda state to become available
- reads the current end-effector pose
- commands one linear move 2 cm forward along +X in the robot base frame
- prints the pose before and after the move
"""

import argparse
import asyncio
import sys
import threading
import time
from pathlib import Path

import rclpy
from rclpy.executors import SingleThreadedExecutor

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from nodes.panda_node import PandaNode  # noqa: E402


def spin_executor(executor: SingleThreadedExecutor) -> None:
    try:
        executor.spin()
    except Exception as exc:
        print(f"[spin] executor error: {exc}", file=sys.stderr)


async def wait_for_pose(node: PandaNode, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pose = node.get_pose_dict()
        joints = node.get_joint_positions()
        if pose is not None and joints is not None:
            return pose
        await asyncio.sleep(0.1)
    raise RuntimeError(
        "Timed out waiting for Panda pose/joint state. "
        "Check the robot connection and FCI access."
    )


async def wait_for_motion_start(node: PandaNode, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if node.is_moving():
            return
        await asyncio.sleep(0.02)
    raise RuntimeError("Panda motion did not start")


async def wait_for_motion_end(node: PandaNode, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not node.is_moving():
            return
        await asyncio.sleep(0.05)
    raise RuntimeError(f"Panda motion did not finish within {timeout_s}s")


async def run_test(delta_x_m: float, velocity: float, acceleration: float, timeout_s: float) -> int:
    rclpy.init()

    node = PandaNode()
    ros_executor = SingleThreadedExecutor()
    ros_executor.add_node(node)
    ros_thread = threading.Thread(target=spin_executor, args=(ros_executor,), daemon=True)
    ros_thread.start()

    try:
        start_pose = await wait_for_pose(node, timeout_s=10.0)
        print(f"Start pose: {start_pose}")

        target_pose = [
            start_pose["x"] + delta_x_m,
            start_pose["y"],
            start_pose["z"],
            start_pose["rx"],
            start_pose["ry"],
            start_pose["rz"],
        ]
        print(
            "Target pose: "
            f"x={target_pose[0]:.4f}, y={target_pose[1]:.4f}, z={target_pose[2]:.4f}, "
            f"rx={target_pose[3]:.4f}, ry={target_pose[4]:.4f}, rz={target_pose[5]:.4f}"
        )

        node.send_movel(
            target_pose,
            accel=acceleration,
            vel=velocity,
        )
        await wait_for_motion_start(node, timeout_s=2.0)
        await wait_for_motion_end(node, timeout_s=timeout_s)

        end_pose = await wait_for_pose(node, timeout_s=2.0)
        success = end_pose is not None
        print(f"Move success: {success}")
        print(f"End pose: {end_pose}")
        return 0 if success else 1
    finally:
        ros_executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move the Panda 2 cm forward in linear motion via the ROS 2 node/executor path."
    )
    parser.add_argument(
        "--delta-x",
        type=float,
        default=0.02,
        help="Linear offset in meters along +X of the robot base frame (default: 0.02).",
    )
    parser.add_argument(
        "--velocity",
        type=float,
        default=0.05,
        help="Linear velocity in m/s (default: 0.05).",
    )
    parser.add_argument(
        "--acceleration",
        type=float,
        default=0.10,
        help="Linear acceleration in m/s^2 (default: 0.10).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Motion timeout in seconds (default: 20).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(
        run_test(
            delta_x_m=args.delta_x,
            velocity=args.velocity,
            acceleration=args.acceleration,
            timeout_s=args.timeout,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
