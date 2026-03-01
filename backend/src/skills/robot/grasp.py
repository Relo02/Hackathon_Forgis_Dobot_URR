"""Grasp skill for Franka Panda gripper with configurable grasp distance."""

from typing import Optional

from pydantic import BaseModel, Field

from ..base import ExecutionContext, Skill, SkillResult
from ..registry import register_skill


class GraspParams(BaseModel):
    """Parameters for the grasp skill."""

    width: float = Field(
        default=0.0,
        ge=0.0,
        le=0.08,
        description="Target grasp width in metres (distance between fingers, 0.0–0.08)",
    )
    speed: float = Field(
        default=0.02,
        ge=0.005,
        le=0.2,
        description="Gripper closing speed in m/s",
    )
    force: float = Field(
        default=20.0,
        ge=1.0,
        le=70.0,
        description="Grasping force in Newtons",
    )


@register_skill
class GraspSkill(Skill[GraspParams]):
    """Grasp an object with the Franka Panda gripper at a specified width and force."""

    name = "grasp"
    executor_type = "robot"
    description = "Grasp an object with the gripper at a specified width (distance between fingers) and force"

    @classmethod
    def params_schema(cls) -> type[BaseModel]:
        return GraspParams

    async def validate(self, params: GraspParams) -> tuple[bool, Optional[str]]:
        return True, None

    async def execute(
        self, params: GraspParams, context: ExecutionContext
    ) -> SkillResult:
        robot_executor = context.get_executor("robot")

        if not hasattr(robot_executor, "grasp"):
            return SkillResult.fail(
                "Current robot executor does not support the grasp command"
            )

        success = await robot_executor.grasp(
            width=params.width,
            speed=params.speed,
            force=params.force,
        )

        if success:
            return SkillResult.ok(
                {
                    "width": params.width,
                    "speed": params.speed,
                    "force": params.force,
                    "grasped": True,
                }
            )
        else:
            return SkillResult.fail(
                "Grasp failed — object may not be present or width mismatch",
                {
                    "width": params.width,
                    "force": params.force,
                    "grasped": False,
                },
            )
