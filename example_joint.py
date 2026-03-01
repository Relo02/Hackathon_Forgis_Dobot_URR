from franky import Robot, JointMotion

robot = Robot("192.168.15.33")  # replace with your robot's FCI IP
robot.recover_from_errors()
robot.relative_dynamics_factor = 0.05  # start slow

# A point-to-point motion in joint space (7 joints, radians)
motion = JointMotion([-0.3, 0.1, 0.3, -1.4, 0.1, 1.8, 0.7])

robot.move(motion)