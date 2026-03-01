"""Executor wrapping PandaNode for motion control."""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from .base import Executor

if TYPE_CHECKING:
    from ..nodes.panda_node import PandaNode

logger = logging.getLogger(__name__)


class PandaExecutor(Executor):
    """
    Executor for Franka Emika Panda motion commands.

    Key differences from UR/DOBOT:
    - 7 DOF (skills must provide 7 joint targets)
    - No External Control / resend pattern — Panda uses franky-control directly
    - Motion completion detected by polling joint stability
    """

    executor_type = "robot"

    def __init__(self, node: "PandaNode"):
        self._node = node
        self._motion_poll_interval = 0.1  # seconds
        logger.info("PandaExecutor initialized")

    async def initialize(self) -> None:
        """Wait for Panda connection."""
        logger.info("PandaExecutor initializing...")
        timeout = 10.0
        elapsed = 0.0
        while self._node.get_joint_positions() is None and elapsed < timeout:
            await asyncio.sleep(0.1)
            elapsed += 0.1

        if self._node.get_joint_positions() is None:
            logger.warning("Panda joint positions not available after timeout")
        else:
            logger.info("PandaExecutor ready")

    async def shutdown(self) -> None:
        pass

    def is_ready(self) -> bool:
        return self._node.get_joint_positions() is not None

    async def _wait_for_motion_start(self, timeout: float = 2.0) -> None:
        """Wait until the background motion thread is actually running."""
        elapsed = 0.0
        while not self._node.is_moving() and elapsed < timeout:
            await asyncio.sleep(0.02)
            elapsed += 0.02

    async def move_joint(
        self,
        target_rad: list[float],
        acceleration: float = 1.4,
        velocity: float = 1.05,
        tolerance_rad: float = 0.02,
        timeout: float = 60.0,
    ) -> bool:
        """
        Execute a joint-space move and wait for completion.

        Args:
            target_rad: Target joint positions in radians (7 values for Panda).
            acceleration: Joint acceleration in rad/s².
            velocity: Joint velocity in rad/s.
            tolerance_rad: Position tolerance in radians.
            timeout: Maximum time to wait for motion completion.

        Returns:
            True if motion completed within tolerance, False on timeout.
        """
        logger.info(f"PandaExecutor: Starting movej to {target_rad}")

        self._node.send_movej(target_rad, accel=acceleration, vel=velocity)

        # Wait for the motion thread to start before polling
        await self._wait_for_motion_start()

        # Poll until target reached or timeout
        elapsed = 0.0
        while elapsed < timeout:
            if self._node.joints_at_target(target_rad, tolerance=tolerance_rad):
                logger.info("PandaExecutor: Joint target reached")
                return True
            await asyncio.sleep(self._motion_poll_interval)
            elapsed += self._motion_poll_interval

        logger.error(f"PandaExecutor: Joint move timeout after {timeout}s")
        return False

    async def move_linear(
        self,
        pose: list[float],
        acceleration: float = 1.2,
        velocity: float = 0.25,
        timeout: float = 60.0,
    ) -> bool:
        """
        Execute a Cartesian linear move and wait for completion.

        Args:
            pose: Target pose [x, y, z, rx, ry, rz] in meters and radians.
            acceleration: Tool acceleration in m/s².
            velocity: Tool velocity in m/s.
            timeout: Maximum time to wait for motion completion.

        Returns:
            True if motion completed (joints stable), False on timeout.
        """
        logger.info(f"PandaExecutor: Starting movel to {pose}")

        self._node.send_movel(pose, accel=acceleration, vel=velocity)

        # Wait for the motion thread to start before polling stability
        await self._wait_for_motion_start()

        # Detect completion by waiting for joints to stop moving
        elapsed = 0.0
        prev_joints = None
        stable_count = 0
        stable_threshold = 3

        while elapsed < timeout:
            await asyncio.sleep(self._motion_poll_interval)
            elapsed += self._motion_poll_interval

            current = self._node.get_joint_positions()
            if current is None:
                continue

            if prev_joints is not None:
                max_diff = max(abs(c - p) for c, p in zip(current, prev_joints))
                if max_diff < 0.001:
                    stable_count += 1
                    if stable_count >= stable_threshold:
                        logger.info(f"PandaExecutor: Linear move complete (stable for {stable_count} polls)")
                        return True
                else:
                    stable_count = 0

            prev_joints = current

        logger.error(f"PandaExecutor: Linear move timeout after {timeout}s")
        return False

    async def open_gripper(self, width: float = 0.08, speed: float = 0.1) -> None:
        """Open gripper to *width* metres at *speed* m/s."""
        logger.info(f"PandaExecutor: Opening gripper (width={width}, speed={speed})")
        self._node.open_gripper(width=width, speed=speed)

    async def close_gripper(self) -> None:
        """Close gripper (grasp)."""
        logger.info("PandaExecutor: Closing gripper")
        self._node.close_gripper()

    async def grasp(
        self,
        width: float = 0.0,
        speed: float = 0.02,
        force: float = 20.0,
        epsilon_outer: float = 1.0,
    ) -> bool:
        """Grasp an object at a specific width with configurable force.

        Args:
            width: Target grasp width in metres (distance between fingers).
            speed: Gripper closing speed in m/s.
            force: Grasping force in Newtons.
            epsilon_outer: Outer tolerance for grasp detection.

        Returns:
            True if grasp succeeded, False otherwise.
        """
        logger.info(
            "PandaExecutor: Grasping (width=%.3fm, speed=%.3fm/s, force=%.1fN)",
            width, speed, force,
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._node.grasp, width, speed, force, epsilon_outer
        )

    async def reset_joints(self) -> None:
        """Blocking move to the canonical home configuration."""
        logger.info("PandaExecutor: Resetting to home position")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._node.reset_joints)
        logger.info("PandaExecutor: Home position reached")

    def get_joint_positions_deg(self) -> Optional[list[float]]:
        return self._node.get_joint_positions_deg()

    def get_pose(self) -> Optional[dict]:
        """Return current EE pose as a JSON-serializable dict, or None."""
        return self._node.get_pose_dict()

    def get_state_summary(self) -> dict:
        return self._node.get_state_summary()
