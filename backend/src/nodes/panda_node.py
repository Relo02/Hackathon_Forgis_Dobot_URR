"""Franka Panda node using franky-control (ROS-free, direct FCI connection).

franky connects directly to the robot over TCP — no ROS stack required.

Install the pre-built wheel (Python 3.12, Ubuntu ≥ 22.04):
    pip install /home/lorenzo/franka-robot/dist/franky_control-1.1.3-cp312-cp312-manylinux_2_28_x86_64.whl

Set ROBOT_IP in .env to the robot's FCI IP (e.g. 10.90.90.1).
Set ROBOT_DYNAMICS (0.0–1.0, default 0.1) to limit speed for safety.

Motion commands run in a background thread (fire-and-forget) so
PandaExecutor can poll for completion without blocking asyncio.
"""

import math
import logging
import os
import threading
import time
from typing import Optional, List
from franky import (
    Affine,
    CartesianMotion,
    Gripper,
    JointMotion,
    ReferenceType,
    Robot,
)
from scipy.spatial.transform import Rotation

logger = logging.getLogger(__name__)

PANDA_NUM_JOINTS = 7
_DEFAULT_IP = "10.90.90.1"
_DEFAULT_DYNAMICS = 0.1   # 10% — safe default for first runs
_HOME_JOINTS = [0.0, -math.pi / 4, 0.0, -3 * math.pi / 4, 0.0, math.pi / 2, math.pi / 4]


class PandaNode:
    """Franka Panda wrapper using franky-control.

    Provides the same synchronous API as DobotNova5Node / RobotNode so
    PandaExecutor, the skill system, and FastAPI routes work unchanged.

    Public interface (consumed by PandaExecutor):
        send_movej(target_rad, accel, vel)
        send_movel(pose, accel, vel)
        get_joint_positions() -> List[float] | None   (radians, 7 DOF)
        get_joint_positions_deg() -> List[float] | None
        joints_at_target(target_rad, tolerance) -> bool
        get_state_summary() -> dict
    """

    def __init__(self):
        ip = os.environ.get("PANDA_IP", _DEFAULT_IP)
        dynamics = float(os.environ.get("ROBOT_DYNAMICS", _DEFAULT_DYNAMICS))

        self._ip = ip
        self._robot: Optional[Robot] = None
        self._gripper: Optional[Gripper] = None
        self._connected = False
        self._motion_thread: Optional[threading.Thread] = None
        self._motion_lock = threading.Lock()

        try:
            logger.info("PandaNode: connecting to %s (dynamics=%.0f%%) …", ip, dynamics * 100)
            self._robot = Robot(ip)
            self._robot.recover_from_errors()
            self._robot.relative_dynamics_factor = dynamics
            self._gripper = Gripper(ip)
            self._connected = True
            logger.info("PandaNode: connected")
        except Exception as exc:
            logger.warning("PandaNode: connection failed — %s", exc)

    # ── Internal: dispatch a blocking franky move to a background thread ─────

    def _run_motion(self, motion) -> None:
        """Start *motion* in a daemon thread and return immediately."""
        def _worker():
            try:
                self._robot.move(motion)
            except Exception as exc:
                logger.error("PandaNode: motion error — %s", exc)

        with self._motion_lock:
            self._motion_thread = threading.Thread(target=_worker, daemon=True)
            self._motion_thread.start()

    # ── Motion commands ──────────────────────────────────────────────────────

    def send_movej(
        self,
        target_rad: List[float],
        accel: float = 1.4,  # noqa: ARG002
        vel: float = 1.05,   # noqa: ARG002
    ) -> None:
        """Joint-space move to *target_rad* (7 radians). Returns immediately."""
        if not self._connected or self._robot is None:
            logger.error("PandaNode.send_movej: not connected")
            return
        logger.info(
            "PandaNode: send_movej %s deg",
            [round(math.degrees(j), 1) for j in target_rad],
        )
        self._run_motion(JointMotion(list(target_rad)))

    def send_movel(
        self,
        pose: List[float],
        accel: float = 1.2,  # noqa: ARG002
        vel: float = 0.25,   # noqa: ARG002
    ) -> None:
        """Cartesian linear move to *pose* = [x, y, z, rx, ry, rz] (m / rad, absolute).

        rx, ry, rz are roll-pitch-yaw (extrinsic XYZ Euler angles).
        Returns immediately; PandaExecutor detects completion via joint
        stability polling.
        """
        if not self._connected or self._robot is None:
            logger.error("PandaNode.send_movel: not connected")
            return
        x, y, z, rx, ry, rz = pose
        quat = Rotation.from_euler("xyz", [rx, ry, rz]).as_quat()  # [x,y,z,w]
        target = Affine([x, y, z], quat)
        logger.info(
            "PandaNode: send_movel xyz=[%.3f, %.3f, %.3f] rpy_deg=[%.1f, %.1f, %.1f]",
            x, y, z, math.degrees(rx), math.degrees(ry), math.degrees(rz),
        )
        self._run_motion(CartesianMotion(target))

    def send_movel_relative(self, delta: List[float]) -> None:
        """Relative Cartesian move. delta = [dx, dy, dz, drx, dry, drz] (m / rad)."""
        if not self._connected or self._robot is None:
            logger.error("PandaNode.send_movel_relative: not connected")
            return
        x, y, z, rx, ry, rz = delta
        quat = Rotation.from_euler("xyz", [rx, ry, rz]).as_quat()
        target = Affine([x, y, z], quat)
        self._run_motion(CartesianMotion(target, ReferenceType.Relative))

    # ── Gripper helpers ───────────────────────────────────────────────────────

    def open_gripper(self, width: float = 0.08, speed: float = 0.1) -> None:
        """Open gripper to *width* metres at *speed* m/s."""
        if self._gripper:
            try:
                self._gripper.move(width, speed)
            except Exception as exc:
                logger.error("PandaNode.open_gripper: %s", exc)

    def close_gripper(self) -> None:
        """Close gripper (grasp)."""
        if self._gripper:
            try:
                self._gripper.grasp(0.0, 0.02, 20.0, epsilon_outer=1.0)
            except Exception as exc:
                logger.error("PandaNode.close_gripper: %s", exc)

    def grasp(
        self,
        width: float = 0.0,
        speed: float = 0.02,
        force: float = 20.0,
        epsilon_outer: float = 1.0,
    ) -> bool:
        """Grasp an object at *width* metres with *force* Newtons.

        Args:
            width: Target grasp width in metres (distance between fingers).
            speed: Gripper closing speed in m/s.
            force: Grasping force in Newtons.
            epsilon_outer: Outer tolerance for successful grasp detection.

        Returns:
            True if grasp succeeded, False otherwise.
        """
        if not self._gripper:
            logger.error("PandaNode.grasp: gripper not available")
            return False
        try:
            return self._gripper.grasp(width, speed, force, epsilon_outer=epsilon_outer)
        except Exception as exc:
            logger.error("PandaNode.grasp: %s", exc)
            return False

    def reset_joints(self) -> None:
        """Blocking move to the canonical home configuration."""
        if self._robot:
            self._robot.move(JointMotion(_HOME_JOINTS))

    # ── State queries ─────────────────────────────────────────────────────────

    def get_joint_positions(self) -> Optional[List[float]]:
        """Return current joint positions in radians (7 DOF), or None."""
        if not self._connected or self._robot is None:
            return None
        try:
            return list(self._robot.state.q)
        except Exception as exc:
            logger.error("PandaNode.get_joint_positions: %s", exc)
            return None

    def get_joint_positions_deg(self) -> Optional[List[float]]:
        """Return current joint positions in degrees, or None."""
        joints = self.get_joint_positions()
        if joints is None:
            return None
        return [math.degrees(j) for j in joints]

    def joints_at_target(
        self, target_rad: List[float], tolerance: float = 0.02
    ) -> bool:
        """True when every joint is within *tolerance* radians of *target_rad*."""
        current = self.get_joint_positions()
        if current is None:
            return False
        return all(abs(c - t) < tolerance for c, t in zip(current, target_rad))

    def is_moving(self) -> bool:
        """True if a background motion thread is still running."""
        with self._motion_lock:
            return self._motion_thread is not None and self._motion_thread.is_alive()

    def get_pose(self) -> Optional[Affine]:
        """Return current end-effector pose as franky.Affine, or None."""
        if not self._connected or self._robot is None:
            return None
        try:
            return self._robot.current_pose
        except Exception as exc:
            logger.error("PandaNode.get_pose: %s", exc)
            return None

    def get_pose_dict(self) -> Optional[dict]:
        """Return current EE pose as a JSON-serializable dict, or None.

        Keys: x, y, z (metres), rx, ry, rz (radians, extrinsic XYZ Euler).
        """
        affine = self.get_pose()
        if affine is None:
            return None
        translation = list(affine.translation)
        rpy = Rotation.from_matrix(affine.rotation).as_euler("xyz").tolist()
        return {
            "x": translation[0],
            "y": translation[1],
            "z": translation[2],
            "rx": rpy[0],
            "ry": rpy[1],
            "rz": rpy[2],
        }

    def get_state_summary(self) -> dict:
        return {
            "timestamp": time.time(),
            "connected": self._connected,
            "joints_deg": self.get_joint_positions_deg(),
            "io": {"digital_in": [], "digital_out": []},
        }

# Uncomment for testing
# def example_sequences():
#     """Example motion sequences — run directly to test against the real robot."""
#     node = PandaNode()
#     if not node._connected:
#         logger.error("PandaNode example: not connected, skipping")
#         return

#     logger.info("PandaNode example: resetting to home")
#     node.reset_joints()

#     logger.info("PandaNode example: moving to joint target")
#     target_rad = [0.0, -0.5, 0.0, 0.2, 0.0, 0.5, 0.0]
#     node.send_movej(target_rad)
#     while not node.joints_at_target(target_rad):
#         time.sleep(0.1)
#     logger.info("PandaNode example: joint target reached — %s deg", node.get_joint_positions_deg())

#     # logger.info("PandaNode example: Cartesian move +5 cm in Z (relative)")
#     # node.send_movel_relative([0, 0, 0.05, 0, 0, 0])
#     # while node.is_moving():
#     #     time.sleep(0.1)
#     # logger.info("PandaNode example: done — pose %s", node.get_pose())

#     logger.info("PandaNode example: returning home")
#     node.reset_joints()


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     example_sequences()
