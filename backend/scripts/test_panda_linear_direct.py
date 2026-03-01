#!/usr/bin/env python3
"""Direct Panda linear smoke test using franky only.

This intentionally avoids:
- ROS 2 nodes/executors
- FastAPI
- flow execution
- camera/OpenAI imports

It is the shortest possible end-to-end check that the container can talk to the
Panda and execute a small relative linear motion.
"""

import argparse
import os
import time

from franky import Affine, CartesianMotion, ReferenceType, Robot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move the Panda a small distance linearly using franky only."
    )
    parser.add_argument(
        "--delta-x",
        type=float,
        default=0.02,
        help="Relative X displacement in metres (default: 0.02).",
    )
    parser.add_argument(
        "--delta-y",
        type=float,
        default=0.0,
        help="Relative Y displacement in metres (default: 0.0).",
    )
    parser.add_argument(
        "--delta-z",
        type=float,
        default=0.0,
        help="Relative Z displacement in metres (default: 0.0).",
    )
    parser.add_argument(
        "--dynamics",
        type=float,
        default=0.005,
        help="franky relative dynamics factor from 0.0 to 1.0 (default: 0.005).",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=1.0,
        help="Seconds to wait after motion for logs/observation (default: 1.0).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    robot_ip = os.environ.get("PANDA_IP", "192.168.15.33")

    print(f"Connecting to Panda at {robot_ip}")
    robot = Robot(robot_ip)
    robot.recover_from_errors()
    robot.relative_dynamics_factor = args.dynamics

    print(
        "Executing relative linear motion: "
        f"dx={args.delta_x:.4f}, dy={args.delta_y:.4f}, dz={args.delta_z:.4f}, "
        f"dynamics={args.dynamics:.4f}"
    )

    motion = CartesianMotion(
        Affine([args.delta_x, args.delta_y, args.delta_z]),
        ReferenceType.Relative,
    )
    robot.move(motion)

    time.sleep(args.settle)
    print("Motion command completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
