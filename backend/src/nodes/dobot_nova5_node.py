"""ROS 2 node wrapper for DOBOT Nova 5 robot arm (driver V4)."""

import math
import time
from typing import Optional, List

from rclpy.node import Node
from sensor_msgs.msg import JointState
from dobot_msgs_v4.srv import MovJ, MovL, EnableRobot, ClearError, ToolDO


# Joint names as published by the DOBOT V4 feedback node on /joint_states_robot.
# Verify at runtime with: ros2 topic echo /joint_states_robot --once
DOBOT_JOINT_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]

# Service namespace (confirmed from DOBOT_6Axis_ROS2_V4 source)
_SRV_PREFIX = "/dobot_bringup_ros2/srv"


class DobotNova5Node(Node):
    """
    Thin ROS 2 node for DOBOT Nova 5 (V4 driver).

    Subscribes to joint state feedback and exposes synchronous motion
    methods (service calls) that can be safely called from a thread pool
    via asyncio.get_event_loop().run_in_executor().

    V4 API notes:
    - MovJ(mode=True,  a-f = J1-J6 degrees)  → joint-space move
    - MovJ(mode=False, a-f = X,Y,Z,Rx,Ry,Rz) → Cartesian point-to-point
    - MovL(a-f = X,Y,Z,Rx,Ry,Rz)             → Cartesian linear move
    - All services return res=0 on success; res=-2 = not in Remote TCP mode
    """

    def __init__(self):
        super().__init__("dobot_nova5_node")

        # Joint state cache (populated by /joint_states_robot subscription)
        self._joint_positions: Optional[dict] = None

        self.create_subscription(
            JointState,
            "/joint_states_robot",
            self._on_joint_states,
            10,
        )

        # Service clients
        self._enable_client = self.create_client(
            EnableRobot, f"{_SRV_PREFIX}/EnableRobot"
        )
        self._movj_client = self.create_client(
            MovJ, f"{_SRV_PREFIX}/MovJ"
        )
        self._movl_client = self.create_client(
            MovL, f"{_SRV_PREFIX}/MovL"
        )
        self._clear_error_client = self.create_client(
            ClearError, f"{_SRV_PREFIX}/ClearError"
        )
        self._tool_do_client = self.create_client(
            ToolDO, f"{_SRV_PREFIX}/ToolDO"
        )

        self.get_logger().info("DobotNova5Node initialized")

    # ── ROS callbacks ────────────────────────────────────────────────────────

    def _on_joint_states(self, msg: JointState) -> None:
        if len(msg.name) == len(msg.position):
            self._joint_positions = dict(zip(msg.name, msg.position))

    # ── Internal: blocking service call helper ───────────────────────────────

    def _call_service(self, client, request, timeout: float = 10.0) -> Optional[object]:
        """
        Call a ROS 2 service synchronously (blocks the calling thread).

        Safe to call from a thread pool (run_in_executor). The MultiThreadedExecutor
        running in a separate thread handles the DDS response callback.

        Returns the response object, or None on timeout/error.
        """
        future = client.call_async(request)
        t0 = time.monotonic()
        while not future.done() and time.monotonic() - t0 < timeout:
            time.sleep(0.05)
        if not future.done():
            self.get_logger().error(
                f"Service call timed out after {timeout}s: {client.srv_name}"
            )
            return None
        return future.result()

    # ── Public sync API ──────────────────────────────────────────────────────

    def enable_robot(self) -> bool:
        """Enable the DOBOT arm. Must be called once before any motion.

        Requires the teach pendant to be in Remote TCP mode (res=-2 otherwise).
        """
        req = EnableRobot.Request()
        resp = self._call_service(self._enable_client, req, timeout=10.0)
        if resp is None:
            return False
        success = resp.res == 0
        if success:
            self.get_logger().info("DOBOT robot enabled")
        else:
            self.get_logger().warning(
                f"EnableRobot returned code {resp.res}"
                + (" (not in Remote TCP mode?)" if resp.res == -2 else "")
            )
        return success

    def clear_error(self) -> bool:
        """Clear active alarms. Call before enable_robot if res=-4."""
        req = ClearError.Request()
        resp = self._call_service(self._clear_error_client, req, timeout=5.0)
        if resp is None:
            return False
        return resp.res == 0

    def tool_do(self, index: int, status: int) -> bool:
        """Control a tool digital output (ToolDO).

        Dual-solenoid pneumatic gripper convention:
          index=1, status=1 → close gripper
          index=2, status=1 → open gripper
        """
        req = ToolDO.Request()
        req.index = index
        req.status = status
        resp = self._call_service(self._tool_do_client, req, timeout=5.0)
        if resp is None:
            return False
        if resp.res != 0:
            self.get_logger().warning(f"ToolDO(index={index}, status={status}) returned code {resp.res}")
            return False
        return True

    def send_joint_move(self, j1: float, j2: float, j3: float,
                        j4: float, j5: float, j6: float) -> bool:
        """
        Send a joint-space move command (degrees) via MovJ with mode=True.

        The service returns quickly after accepting the command — motion is
        still in progress. Completion is detected by polling joint stability
        in the executor.
        """
        req = MovJ.Request()
        req.mode = True  # True = joint space (a-f are J1-J6 in degrees)
        req.a = float(j1)
        req.b = float(j2)
        req.c = float(j3)
        req.d = float(j4)
        req.e = float(j5)
        req.f = float(j6)
        resp = self._call_service(self._movj_client, req, timeout=5.0)
        if resp is None:
            return False
        if resp.res != 0:
            self.get_logger().warning(f"MovJ (joint) returned code {resp.res}")
            return False
        return True

    def send_linear_move(self, x: float, y: float, z: float,
                         rx: float, ry: float, rz: float) -> bool:
        """
        Send a Cartesian linear move command via MovL.

        Units expected by DOBOT firmware: x/y/z in mm, rx/ry/rz in degrees.
        The executor is responsible for converting from SI units (m, rad).

        The service returns quickly after accepting; completion detected by
        polling joint stability in the executor.
        """
        req = MovL.Request()
        req.a = float(x)
        req.b = float(y)
        req.c = float(z)
        req.d = float(rx)
        req.e = float(ry)
        req.f = float(rz)
        resp = self._call_service(self._movl_client, req, timeout=5.0)
        if resp is None:
            return False
        if resp.res != 0:
            self.get_logger().warning(f"MovL returned code {resp.res}")
            return False
        return True

    # ── State queries ────────────────────────────────────────────────────────

    def get_joint_positions(self) -> Optional[List[float]]:
        """Return current joint positions in radians, or None if not yet received.

        The V4 feedback node publishes values already converted to radians.
        """
        if self._joint_positions is None:
            return None
        return [self._joint_positions.get(name, 0.0) for name in DOBOT_JOINT_NAMES]

    def get_joint_positions_deg(self) -> Optional[List[float]]:
        """Return current joint positions in degrees, or None if not yet received."""
        if self._joint_positions is None:
            return None
        return [math.degrees(self._joint_positions.get(name, 0.0))
                for name in DOBOT_JOINT_NAMES]

    def joints_at_target(self, target_deg: List[float], tolerance_deg: float = 1.0) -> bool:
        """Check whether each joint is within tolerance of target (degrees)."""
        current_deg = self.get_joint_positions_deg()
        if current_deg is None:
            return False
        return all(abs(c - t) < tolerance_deg for c, t in zip(current_deg, target_deg))

    def get_state_summary(self) -> dict:
        return {
            "timestamp": time.time(),
            "robot_type": "dobot",
            "joint_count": 6,
            "connected": self._joint_positions is not None,
            "joints_deg": self.get_joint_positions_deg(),
            "io": {"digital_in": [], "digital_out": []},
        }
