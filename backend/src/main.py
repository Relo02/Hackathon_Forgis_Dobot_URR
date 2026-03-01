import asyncio
import logging
import os
import threading

import rclpy
import uvicorn
from rclpy.executors import MultiThreadedExecutor

from api.app import create_app
from api.websocket import WebSocketManager
from executors import IOExecutor, RobotExecutor, PandaExecutor, CameraExecutor, HandExecutor, DobotNova5Executor
from flow.manager import FlowManager
from nodes.ur_node import RobotNode
from nodes.dobot_nova5_node import DobotNova5Node
from nodes.panda_node import PandaNode
from nodes.camera_node import CameraNode
from nodes.camera_bridge_node import CameraBridgeNode
from nodes.covvi_hand_node import CovviHandNode
# Import skills to register them
import skills.robot  # noqa: F401
import skills.io  # noqa: F401
import skills.camera  # noqa: F401
import skills.hand  # noqa: F401

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_ros_executor(ros_executor: MultiThreadedExecutor) -> None:
    """Run the ROS 2 executor in a separate thread."""
    try:
        ros_executor.spin()
    except Exception as e:
        logger.error(f"ROS executor error: {e}")


def main():
    rclpy.init()

    # Select robot type from environment (ur | dobot | panda)
    robot_type = os.environ.get("ROBOT_TYPE", "panda").lower()
    logger.info(f"Robot type: {robot_type}")

    # ROS 2 robot node + executor (type-switched)
    if robot_type == "panda":
        print("HELO1")
        robot = PandaNode()
        robot_executor = PandaExecutor(robot)
        io_robot_executor = None  # Panda I/O can be wired later
        logger.info("Using Panda HELO2 robot")
    elif robot_type == "dobot":
        robot = DobotNova5Node()
        robot_executor = DobotNova5Executor(robot)
        io_robot_executor = None  # DOBOT I/O can be wired later
        logger.info("Using DOBOT Nova 5 robot")
    else:
        robot = RobotNode()
        robot_executor = RobotExecutor(robot)
        io_robot_executor = IOExecutor(robot, executor_type="io_robot")
        logger.info("Using UR robot")

    # Fixed ROS 2 nodes
    camera = CameraNode()
    camera_bridge = CameraBridgeNode()
    hand = CovviHandNode()

    # WebSocket manager for real-time events
    ws_manager = WebSocketManager()

    # Camera and hand executors (always present)
    camera_executor = CameraExecutor(camera, ws_manager)
    hand_executor = HandExecutor(hand)

    executors = {
        "robot": robot_executor,
        "camera": camera_executor,
        "hand": hand_executor,
    }
    if io_robot_executor is not None:
        executors["io_robot"] = io_robot_executor

    # Flow manager for orchestration
    flows_dir = os.environ.get("FLOWS_DIR", "/app/flows")
    flow_manager = FlowManager(
        executors=executors,
        ws_manager=ws_manager,
        flows_dir=flows_dir,
    )

    # FastAPI application
    app = create_app(flow_manager, ws_manager, robot, camera_executor, io_robot_executor, hand_executor)

    # ROS 2 executor with nodes
    ros_executor = MultiThreadedExecutor()
    ros_executor.add_node(robot)
    ros_executor.add_node(camera)
    ros_executor.add_node(camera_bridge)
    ros_executor.add_node(hand)
    # Run ROS 2 executor in background thread
    ros_thread = threading.Thread(target=run_ros_executor, args=(ros_executor,), daemon=True)
    ros_thread.start()
    logger.info("ROS 2 executor started in background thread")

    # Initialize executors asynchronously
    async def init_executors():
        await robot_executor.initialize()
        if io_robot_executor is not None:
            await io_robot_executor.initialize()
        await camera_executor.initialize()
        await hand_executor.initialize()

    asyncio.get_event_loop().run_until_complete(init_executors())
    logger.info("Executors initialized")

    # Run FastAPI server (blocks main thread)
    try:
        logger.info("Starting FastAPI server on port 8000")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        logger.info("Shutting down...")
        ros_executor.shutdown()
        robot.destroy_node()
        camera.destroy_node()
        camera_bridge.destroy_node()
        hand.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
