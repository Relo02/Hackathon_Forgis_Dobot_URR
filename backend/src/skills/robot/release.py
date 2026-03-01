"""Release skill for Franka Panda gripper using Franky's open() semantics."""

from typing import Optional

from pydantic import BaseModel, Field

from ..base import ExecutionContext, Skill, SkillResult
from ..registry import register_skill


class ReleaseParams(BaseModel):
    """Parameters for the release skill."""

    speed: float = Field(
        default=0.06,
        ge=0.005,
        le=0.2,
        description="Gripper opening speed in m/s",
    )


@register_skill
class ReleaseSkill(Skill[ReleaseParams]):
    """Release an object by opening the gripper."""

    name = "release"
    executor_type = "robot"
    description = "Open the gripper to release the current object"

    @classmethod
    def params_schema(cls) -> type[BaseModel]:
        return ReleaseParams

    async def validate(self, params: ReleaseParams) -> tuple[bool, Optional[str]]:
        return True, None

    async def execute(
        self, params: ReleaseParams, context: ExecutionContext
    ) -> SkillResult:
        robot_executor = context.get_executor("robot")

        if not hasattr(robot_executor, "release_gripper"):
            return SkillResult.fail(
                "Current robot executor does not support the release command"
            )

        try:
            await robot_executor.release_gripper(speed=params.speed)
            gripper_width = None
            if hasattr(robot_executor, "get_gripper_width"):
                try:
                    gripper_width = robot_executor.get_gripper_width()
                except Exception:
                    gripper_width = None

            return SkillResult.ok(
                {
                    "speed": params.speed,
                    "released": True,
                    "gripper_width": gripper_width,
                }
            )
        except Exception as exc:
            return SkillResult.fail(
                f"Release failed: {exc}",
                {"speed": params.speed, "released": False},
            )
