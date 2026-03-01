"""Condition evaluator for conditional transitions.

Supports conditions based on:
- IO states: io_robot.input[0], io_robot.output[1]
- Variables: {{label_data.label}}, {{some_var}}
- Comparisons: ==, !=, and, or

Examples:
    "io_robot.input[0] == true"
    "io_robot.output[1] == false"
    "{{label_data.label}} == 'product_A'"
    "io_robot.input[0] == true and io_robot.output[1] == false"
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from executors import Executor

logger = logging.getLogger(__name__)

# Pattern for IO access: io_robot.input[0], io_robot.output[1]
IO_PATTERN = re.compile(r"io_robot\.(input|output)\[(\d+)\]")

# Pattern for variable interpolation: {{var_name}} or {{var.nested.path}}
VAR_PATTERN = re.compile(r"\{\{([\w.]+)\}\}")


def _get_nested_value(variables: dict, path: str) -> Any:
    """Get a value from variables using dot notation."""
    parts = path.split(".")
    value = variables
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    return value


def _resolve_io_value(
    match: re.Match, executors: dict[str, "Executor"]
) -> Optional[bool]:
    """Resolve an IO pattern match to its current value."""
    io_type = match.group(1)  # "input" or "output"
    pin = int(match.group(2))

    executor = executors.get("io_robot")

    if executor is None:
        # logger.warning("Executor 'io_robot' not found for condition")
        return None

    # Access the IO state synchronously from cached values
    # IOExecutor wraps nodes that have _io_states cached
    node = executor._node

    if io_type == "input":
        return node.get_digital_input(pin)
    else:
        return node.get_digital_output(pin)


def _parse_value(token: str) -> Any:
    """Parse a value token to its Python equivalent."""
    token = token.strip()

    if token.lower() == "true":
        return True
    elif token.lower() == "false":
        return False
    elif token.lower() == "none" or token.lower() == "null":
        return None

    # Try numeric
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        pass

    # String (with or without quotes)
    if (token.startswith("'") and token.endswith("'")) or (
        token.startswith('"') and token.endswith('"')
    ):
        return token[1:-1]

    return token


def _evaluate_comparison(left: Any, op: str, right: Any) -> bool:
    """Evaluate a comparison between two values."""
    if op == "==":
        return left == right
    elif op == "!=":
        return left != right
    elif op == ">":
        return left > right if left is not None and right is not None else False
    elif op == "<":
        return left < right if left is not None and right is not None else False
    elif op == ">=":
        return left >= right if left is not None and right is not None else False
    elif op == "<=":
        return left <= right if left is not None and right is not None else False
    else:
        logger.warning(f"Unknown operator: {op}")
        return False


def _resolve_token(
    token: str, variables: dict, executors: dict[str, "Executor"]
) -> Any:
    """Resolve a token to its value (IO, variable, or literal)."""
    token = token.strip()

    # Check for IO pattern
    io_match = IO_PATTERN.fullmatch(token)
    if io_match:
        return _resolve_io_value(io_match, executors)

    # Check for variable pattern
    var_match = VAR_PATTERN.fullmatch(token)
    if var_match:
        return _get_nested_value(variables, var_match.group(1))

    # Otherwise, parse as literal value
    return _parse_value(token)


def evaluate_condition(
    condition: str,
    variables: dict,
    executors: dict[str, "Executor"],
) -> bool:
    """
    Evaluate a condition expression.

    Args:
        condition: The condition string to evaluate
        variables: Flow runtime variables
        executors: Dict of executors for IO access

    Returns:
        True if condition is met, False otherwise

    Examples:
        "io_robot.input[0] == true"
        "io_machine.input[1] == false"
        "{{label_data.label}} == 'product_A'"
        "io_robot.input[0] == true and io_machine.input[1] == false"
    """
    if not condition or not condition.strip():
        return True  # Empty condition is always true

    condition = condition.strip()
    logger.debug(f"Evaluating condition: {condition}")

    # Handle 'and' / 'or' (simple left-to-right, no precedence)
    # Split on ' and ' first, then handle ' or ' within each part
    if " or " in condition.lower():
        parts = re.split(r"\s+or\s+", condition, flags=re.IGNORECASE)
        for part in parts:
            if evaluate_condition(part, variables, executors):
                return True
        return False

    if " and " in condition.lower():
        parts = re.split(r"\s+and\s+", condition, flags=re.IGNORECASE)
        for part in parts:
            if not evaluate_condition(part, variables, executors):
                return False
        return True

    # Single comparison: left op right
    # Supported operators: ==, !=, >, <, >=, <=
    comparison_match = re.match(
        r"(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)", condition
    )
    if comparison_match:
        left_token = comparison_match.group(1)
        op = comparison_match.group(2)
        right_token = comparison_match.group(3)

        left_value = _resolve_token(left_token, variables, executors)
        right_value = _resolve_token(right_token, variables, executors)

        result = _evaluate_comparison(left_value, op, right_value)
        # logger.info(
        #     f"Condition check: {left_token}={left_value} {op} {right_token}={right_value} -> {result}"
        # )
        return result

    # Single token (truthy check)
    value = _resolve_token(condition, variables, executors)
    return bool(value)
