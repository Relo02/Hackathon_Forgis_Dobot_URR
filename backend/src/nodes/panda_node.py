"""ROS 2 node wrapper for Franka Panda motion via franky-control.

This keeps the Panda integration aligned with the rest of the backend:
- it is a real ``rclpy`` node
- it is added to the shared ROS 2 executor in ``main.py``
- it exposes the same synchronous API the Panda executor already uses

Motion commands follow the same ``franky`` patterns shown in
``example_joint.py`` and ``example_linear.py``:
- joint moves use ``JointMotion``
- linear moves use ``CartesianMotion(..., ReferenceType.Relative)``

The rest of the backend still treats this like the UR and DOBOT nodes:
the executor calls ``send_movej()``, ``send_movel()``, and polls cached state.
"""

import logging
import math
import os
import threading
import time
from typing import Optional

import numpy as np
from franky import Affine, CartesianMotion, Gripper, JointMotion, ReferenceType, Robot
from rclpy.node import Node

logger = logging.getLogger(__name__)

PANDA_NUM_JOINTS = 7
DEFAULT_PANDA_IP = "192.168.15.33"
DEFAULT_DYNAMICS = 0.005
MIN_DYNAMICS = 0.002
MAX_DYNAMICS = 0.05
DEFAULT_STATE_POLL_HZ = 20.0
HOME_JOINTS = [0.0, -math.pi / 4, 0.0, 0.0, 0.0, math.pi / 2, math.pi / 4]


def _rotation_matrix_from_xyz_euler(rx: float, ry: float, rz: float) -> np.ndarray:
    """Build a rotation matrix from extrinsic XYZ Euler angles."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    rot_x = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    rot_y = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    rot_z = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]])
    return rot_z @ rot_y @ rot_x


def _xyz_euler_from_rotation_matrix(rotation: np.ndarray) -> list[float]:
    """Convert a rotation matrix to extrinsic XYZ Euler angles."""
    sy = -rotation[2, 0]
    cy = math.sqrt(max(0.0, 1.0 - sy * sy))

    if cy > 1e-6:
        rx = math.atan2(rotation[2, 1], rotation[2, 2])
        ry = math.asin(sy)
        rz = math.atan2(rotation[1, 0], rotation[0, 0])
    else:
        # Gimbal lock fallback.
        rx = math.atan2(-rotation[1, 2], rotation[1, 1])
        ry = math.asin(sy)
        rz = 0.0

    return [rx, ry, rz]


def _quaternion_xyzw_from_rotation_matrix(rotation: np.ndarray) -> list[float]:
    """Convert a rotation matrix to an XYZW quaternion."""
    trace = float(rotation[0, 0] + rotation[1, 1] + rotation[2, 2])
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (rotation[2, 1] - rotation[1, 2]) / s
        qy = (rotation[0, 2] - rotation[2, 0]) / s
        qz = (rotation[1, 0] - rotation[0, 1]) / s
    elif rotation[0, 0] > rotation[1, 1] and rotation[0, 0] > rotation[2, 2]:
        s = math.sqrt(1.0 + rotation[0, 0] - rotation[1, 1] - rotation[2, 2]) * 2.0
        qw = (rotation[2, 1] - rotation[1, 2]) / s
        qx = 0.25 * s
        qy = (rotation[0, 1] + rotation[1, 0]) / s
        qz = (rotation[0, 2] + rotation[2, 0]) / s
    elif rotation[1, 1] > rotation[2, 2]:
        s = math.sqrt(1.0 + rotation[1, 1] - rotation[0, 0] - rotation[2, 2]) * 2.0
        qw = (rotation[0, 2] - rotation[2, 0]) / s
        qx = (rotation[0, 1] + rotation[1, 0]) / s
        qy = 0.25 * s
        qz = (rotation[1, 2] + rotation[2, 1]) / s
    else:
        s = math.sqrt(1.0 + rotation[2, 2] - rotation[0, 0] - rotation[1, 1]) * 2.0
        qw = (rotation[1, 0] - rotation[0, 1]) / s
        qx = (rotation[0, 2] + rotation[2, 0]) / s
        qy = (rotation[1, 2] + rotation[2, 1]) / s
        qz = 0.25 * s

    quaternion = np.array([qx, qy, qz, qw], dtype=float)
    norm = np.linalg.norm(quaternion)
    if norm <= 1e-9:
        return [0.0, 0.0, 0.0, 1.0]
    return (quaternion / norm).tolist()


def _extract_pose_components(pose_obj) -> tuple[Optional[list[float]], Optional[np.ndarray]]:
    """Best-effort extraction of translation/rotation from different franky pose shapes."""
    if pose_obj is None:
        return None, None

    if hasattr(pose_obj, "pose"):
        return _extract_pose_components(pose_obj.pose)

    if hasattr(pose_obj, "end_effector_pose"):
        return _extract_pose_components(pose_obj.end_effector_pose)

    translation = None
    if hasattr(pose_obj, "translation"):
        try:
            translation = list(pose_obj.translation)
        except Exception:
            translation = None

    rotation = None
    if hasattr(pose_obj, "rotation"):
        try:
            rotation = np.array(pose_obj.rotation, dtype=float)
        except Exception:
            rotation = None

    if translation is not None and rotation is not None:
        return translation, rotation

    return None, None


class PandaNode(Node):
    """ROS 2 node that wraps direct Panda control and caches robot state."""

    def __init__(self):
        super().__init__("panda_node")

        self._ip = os.environ.get("PANDA_IP", DEFAULT_PANDA_IP)
        self._dynamics = min(
            MAX_DYNAMICS,
            max(MIN_DYNAMICS, float(os.environ.get("ROBOT_DYNAMICS", DEFAULT_DYNAMICS))),
        )
        self._state_poll_hz = float(
            os.environ.get("PANDA_STATE_POLL_HZ", DEFAULT_STATE_POLL_HZ)
        )

        self._robot: Optional[Robot] = None
        self._gripper: Optional[Gripper] = None
        self._connected = False
        self._running = True
        self._lock = threading.Lock()

        self._motion_thread: Optional[threading.Thread] = None
        self._joint_positions: Optional[list[float]] = None
        self._pose_translation: Optional[list[float]] = None
        self._pose_rotation: Optional[np.ndarray] = None
        self._last_error: Optional[str] = None

        self._connect_thread = threading.Thread(
            target=self._connection_loop,
            daemon=True,
        )
        self._connect_thread.start()

        self.create_timer(1.0 / self._state_poll_hz, self._refresh_state)

        self.get_logger().info(
            f"PandaNode initialized - target={self._ip}, dynamics={self._dynamics:.3f}"
        )

    def _connection_loop(self) -> None:
        """Keep trying to establish the direct Panda connection."""
        while self._running:
            if self._connected:
                time.sleep(1.0)
                continue

            try:
                self.get_logger().info(f"Connecting to Panda at {self._ip}")
                robot = Robot(self._ip)
                robot.recover_from_errors()
                robot.relative_dynamics_factor = self._dynamics
                gripper = Gripper(self._ip)

                with self._lock:
                    self._robot = robot
                    self._gripper = gripper
                    self._connected = True
                    self._last_error = None

                self.get_logger().info("Connected to Panda")
            except Exception as exc:
                self._last_error = str(exc)
                self.get_logger().warning(
                    f"Panda connection failed: {exc}",
                    throttle_duration_sec=10.0,
                )
                time.sleep(2.0)

    def _refresh_state(self) -> None:
        """Cache the latest joint and pose state for executor polling."""
        if not self._connected:
            return

        try:
            joints, translation, rotation = self._read_robot_state()
            if joints is None or translation is None or rotation is None:
                return

            with self._lock:
                self._joint_positions = joints
                self._pose_translation = translation
                self._pose_rotation = rotation
        except Exception as exc:
            self._last_error = str(exc)
            self.get_logger().warning(
                f"Failed to refresh Panda state: {exc}",
                throttle_duration_sec=5.0,
            )

    def _read_robot_state(
        self,
    ) -> tuple[Optional[list[float]], Optional[list[float]], Optional[np.ndarray]]:
        """Read the latest joint and Cartesian state directly from franky."""
        with self._lock:
            robot = self._robot

        if robot is None:
            return None, None, None

        joints = None
        try:
            if hasattr(robot, "current_joint_state"):
                joints = list(robot.current_joint_state.position)
        except Exception:
            joints = None

        if joints is None:
            try:
                joints = list(robot.state.q)
            except Exception:
                joints = None

        translation = None
        rotation = None

        try:
            if hasattr(robot, "current_cartesian_state"):
                cartesian_state = robot.current_cartesian_state
                translation, rotation = _extract_pose_components(cartesian_state)
        except Exception:
            translation = None
            rotation = None

        if translation is None or rotation is None:
            try:
                translation, rotation = _extract_pose_components(robot.current_pose)
            except Exception:
                translation = None
                rotation = None

        return joints, translation, rotation

    def _recover_from_errors(self) -> None:
        with self._lock:
            robot = self._robot
        if robot is None:
            return
        try:
            robot.recover_from_errors()
        except Exception as exc:
            self.get_logger().warning(f"Panda recover_from_errors failed: {exc}")

    def _compute_dynamics_factor(
        self,
        accel: float,
        vel: float,
        *,
        accel_reference: float,
        velocity_reference: float,
    ) -> float:
        requested_scale = min(
            1.0,
            max(0.0, accel / accel_reference),
            max(0.0, vel / velocity_reference),
        )
        return min(self._dynamics, max(MIN_DYNAMICS, self._dynamics * requested_scale))

    def _start_motion(self, motion, label: str, dynamics_factor: float) -> None:
        """Run a blocking franky move in a background thread."""

        def worker() -> None:
            try:
                with self._lock:
                    robot = self._robot

                if robot is None:
                    self._last_error = "Robot not connected"
                    self.get_logger().error(f"{label}: robot not connected")
                    return

                robot.relative_dynamics_factor = dynamics_factor
                self._recover_from_errors()
                robot.move(motion)
            except Exception as exc:
                self._last_error = str(exc)
                self.get_logger().error(f"{label} failed: {exc}")
            finally:
                self._refresh_state()

        with self._lock:
            if self._motion_thread is not None and self._motion_thread.is_alive():
                raise RuntimeError("Panda is already executing another motion")
            self._last_error = None
            self._motion_thread = threading.Thread(target=worker, daemon=True)
            self._motion_thread.start()

    def _current_pose_snapshot(self) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        with self._lock:
            if self._pose_translation is None or self._pose_rotation is None:
                translation = None
                rotation = None
            else:
                translation = np.array(self._pose_translation, dtype=float)
                rotation = np.array(self._pose_rotation, dtype=float)

        if translation is not None and rotation is not None:
            return translation, rotation

        live_joints, live_translation, live_rotation = self._read_robot_state()
        if live_joints is None or live_translation is None or live_rotation is None:
            return None, None

        with self._lock:
            self._joint_positions = live_joints
            self._pose_translation = live_translation
            self._pose_rotation = live_rotation

        return np.array(live_translation, dtype=float), np.array(live_rotation, dtype=float)

    def send_movej(
        self,
        target_rad: list[float],
        accel: float = 1.4,
        vel: float = 1.05,
    ) -> None:
        """Dispatch a joint-space move using franky's JointMotion."""
        if len(target_rad) != PANDA_NUM_JOINTS:
            raise ValueError(
                f"PandaNode.send_movej expected {PANDA_NUM_JOINTS} joints, got {len(target_rad)}"
            )
        if not self._connected:
            self.get_logger().error("Panda send_movej requested while disconnected")
            return

        dynamics_factor = self._compute_dynamics_factor(
            accel,
            vel,
            accel_reference=2.0,
            velocity_reference=2.0,
        )
        self.get_logger().info(
            "Panda joint move: "
            f"{[round(math.degrees(joint), 1) for joint in target_rad]} deg "
            f"(dynamics={dynamics_factor:.3f})"
        )
        self._start_motion(JointMotion(list(target_rad)), "send_movej", dynamics_factor)

    def send_movel(
        self,
        pose: list[float],
        accel: float = 1.2,
        vel: float = 0.25,
    ) -> None:
        """Dispatch an absolute Cartesian move using a relative franky motion.

        The backend skill API supplies an absolute pose [x, y, z, rx, ry, rz].
        The franky example in this repo uses relative Cartesian motion, so this
        method converts the absolute target into a relative transform from the
        current end-effector pose, then sends ``CartesianMotion(..., Relative)``.
        """
        if len(pose) != 6:
            raise ValueError(f"PandaNode.send_movel expected 6 pose values, got {len(pose)}")
        if not self._connected:
            self.get_logger().error("Panda send_movel requested while disconnected")
            return

        dynamics_factor = self._compute_dynamics_factor(
            accel,
            vel,
            accel_reference=3.0,
            velocity_reference=1.0,
        )
        current_translation, current_rotation = self._current_pose_snapshot()
        if current_translation is None or current_rotation is None:
            # Fall back to franky's verified relative Cartesian path when no
            # live Panda pose is available from the local python bindings.
            relative_translation = np.array(pose[:3], dtype=float)
            relative_rotation = np.eye(3, dtype=float)
            relative_quaternion = _quaternion_xyzw_from_rotation_matrix(relative_rotation)
            self.get_logger().warning(
                "Current Panda pose is unavailable; interpreting move_linear target_pose as a relative XYZ move"
            )
        else:
            target_translation = np.array(pose[:3], dtype=float)
            target_rotation = _rotation_matrix_from_xyz_euler(*pose[3:])

            relative_translation = current_rotation.T @ (target_translation - current_translation)
            relative_rotation = current_rotation.T @ target_rotation
            relative_quaternion = _quaternion_xyzw_from_rotation_matrix(relative_rotation)

        self.get_logger().info(
            "Panda linear move: "
            f"xyz=[{pose[0]:.3f}, {pose[1]:.3f}, {pose[2]:.3f}] "
            f"rpy_deg=[{math.degrees(pose[3]):.1f}, {math.degrees(pose[4]):.1f}, {math.degrees(pose[5]):.1f}] "
            f"(dynamics={dynamics_factor:.3f})"
        )

        motion = CartesianMotion(
            Affine(relative_translation.tolist(), relative_quaternion),
            ReferenceType.Relative,
        )
        self._start_motion(motion, "send_movel", dynamics_factor)

    def open_gripper(self, width: float = 0.08, speed: float = 0.1) -> None:
        with self._lock:
            gripper = self._gripper
        if gripper is None:
            raise RuntimeError("Panda gripper not connected")
        gripper.move(width, speed)

    def close_gripper(self) -> None:
<<<<<<< HEAD
        with self._lock:
            gripper = self._gripper
        if gripper is None:
            raise RuntimeError("Panda gripper not connected")
        gripper.grasp()
=======
        """Close gripper (grasp)."""
        if self._gripper:
            try:
                self._gripper.grasp(0.0, 0.02, 20.0, epsilon_outer=1.0)
            except Exception as exc:
                logger.error("PandaNode.close_gripper: %s", exc)
>>>>>>> ec791e03bd37fb3a16b7f615d29701d97da48878

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
        self.send_movej(HOME_JOINTS)
        while self.is_moving():
            time.sleep(0.05)

    def get_joint_positions(self) -> Optional[list[float]]:
        with self._lock:
            cached = None if self._joint_positions is None else list(self._joint_positions)

        if cached is not None:
            return cached

        joints, translation, rotation = self._read_robot_state()
        if joints is None:
            return None

        with self._lock:
            self._joint_positions = joints
            if translation is not None:
                self._pose_translation = translation
            if rotation is not None:
                self._pose_rotation = rotation
        return list(joints)

    def get_joint_positions_deg(self) -> Optional[list[float]]:
        joints = self.get_joint_positions()
        if joints is None:
            return None
        return [math.degrees(joint) for joint in joints]

    def joints_at_target(self, target_rad: list[float], tolerance: float = 0.02) -> bool:
        current = self.get_joint_positions()
        if current is None:
            return False
        return all(abs(current_joint - target_joint) < tolerance for current_joint, target_joint in zip(current, target_rad))

    def is_moving(self) -> bool:
        with self._lock:
            return self._motion_thread is not None and self._motion_thread.is_alive()

    def is_connected(self) -> bool:
        return self._connected

    def get_last_error(self) -> Optional[str]:
        return self._last_error

    def get_connection_target(self) -> str:
        return self._ip

    def get_pose_dict(self) -> Optional[dict]:
        try:
            translation, rotation = self._current_pose_snapshot()
            if translation is None or rotation is None:
                return None
            rx, ry, rz = _xyz_euler_from_rotation_matrix(rotation)
            return {
                "x": float(translation[0]),
                "y": float(translation[1]),
                "z": float(translation[2]),
                "rx": rx,
                "ry": ry,
                "rz": rz,
            }
        except Exception as exc:
            self._last_error = str(exc)
            self.get_logger().warning(
                f"Failed to build Panda pose dict: {exc}",
                throttle_duration_sec=5.0,
            )
            return None

    def get_state_summary(self) -> dict:
        try:
            joints_deg = self.get_joint_positions_deg()
        except Exception as exc:
            self._last_error = str(exc)
            self.get_logger().warning(
                f"Failed to read Panda joints: {exc}",
                throttle_duration_sec=5.0,
            )
            joints_deg = None

        try:
            pose = self.get_pose_dict()
        except Exception as exc:
            self._last_error = str(exc)
            self.get_logger().warning(
                f"Failed to read Panda pose: {exc}",
                throttle_duration_sec=5.0,
            )
            pose = None

        return {
            "timestamp": time.time(),
            "robot_type": "panda",
            "joint_count": PANDA_NUM_JOINTS,
            "connected": self._connected,
            "ip": self._ip,
            "joints_deg": joints_deg,
            "pose": pose,
            "moving": self.is_moving(),
            "last_error": self._last_error,
            "io": {"digital_in": [], "digital_out": []},
        }

    def destroy_node(self) -> bool:
        self._running = False
        return super().destroy_node()
