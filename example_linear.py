from franky import Robot, CartesianMotion, Affine, ReferenceType

robot = Robot("192.168.15.33")  # replace with your robot's FCI IP
robot.recover_from_errors()
robot.relative_dynamics_factor = 0.005  # start slow

# A linear motion in Cartesian space relative to the initial end-effector pose
motion = CartesianMotion(Affine([-0.2, 0.0, 0.0]), ReferenceType.Relative)

robot.move(motion)