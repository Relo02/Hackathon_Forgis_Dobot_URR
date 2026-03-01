from franky import Affine, CartesianMotion, Robot, ReferenceType

robot = Robot("192.168.15.33")
robot.relative_dynamics_factor = 0.05

motion = CartesianMotion(Affine([0.2, 0.0, 0.0]), ReferenceType.Relative)
robot.move(motion)