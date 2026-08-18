from typing import Any, Callable
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict



# ============================================================
# Dynamic decomposition decision
# ============================================================

class DynamicDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    done: bool
    next_task: str

# ============================================================
# Dynamic Decomposition
#
# IMPORTANT:
# The planner decides ONE task at a time.
# The task is executed by the real MCP/tool executor.
# The result becomes an observation for the next decision.
#
# This preserves the original toolkit interface/logic while
# adapting execution to the Brightpeak MCP server.
# ============================================================
def dynamic_decomposition(
    goal: str,
    llm: BaseChatModel,
    task_executor: Callable[[str], Any],
    max_steps: int = 4,
) -> list[tuple[str, str]]:
    """
    Dynamically decompose and execute a Brightpeak task.

    Flow:

        Goal
          ↓
        Decide next task
          ↓
        Execute through real MCP/tool layer
          ↓
        Observe result
          ↓
        Decide next task
          ↓
        ...

    Args:
        goal:
            The original Brightpeak user request.

        llm:
            The existing LLM used by the planning toolkit.

        task_executor:
            Function responsible for executing a generated sub-task
            against the real Brightpeak MCP server/tools.

        max_steps:
            Hard limit preventing an unbounded planning loop.

    Returns:
        A list of:
            (sub_task, observation)

    Example:

        history = dynamic_decomposition(
            goal="Create an academic intervention plan for student 1",
            llm=llm,
            task_executor=execute_brightpeak_task,
        )
    """

    history: list[tuple[str, str]] = []
    for step in range(max_steps):

        # ----------------------------------------------------
        # Build observations from previously executed tasks.
        # ----------------------------------------------------

        observation = (
            "\n".join(
                f"{task}: {result}"
                for task, result in history
            )
            or "None"
        )

        # ----------------------------------------------------
        # Dynamic planning:
        # decide ONLY the next task based on what has already
        # happened.
        # ----------------------------------------------------

        decision = llm.with_structured_output(
            DynamicDecision,
            method="json_schema",
        ).invoke(
            [
                (
                    "system",
                    """
You are the dynamic planning component of the
Brightpeak Academy agent.

Use the observations from previously executed tasks.

Do NOT assume that the original plan is still valid.
If an observation changes what should happen next,
adapt the plan.

Set done=true only when the original goal has been
sufficiently completed.

When done=true, next_task must be an empty string.
""",
                ),
                (
                    "human",
                    f"""
Goal:
{goal}

Completed work and observations:
{observation}

Choose the single best next sub-task.

Return:
- done=true and next_task="" if the goal is complete
- otherwise done=false and a concrete next_task
""",
                ),
            ],
            temperature=0.1,
        )

        # ----------------------------------------------------
        # Goal completed
        # ----------------------------------------------------

        if decision.done:
            break

        task = decision.next_task.strip()

        if not task:
            raise ValueError(
                f"Dynamic planner omitted next_task "
                f"at step {step + 1}"
            )

        # ----------------------------------------------------
        # REAL EXECUTION
        #
        # This is the important integration point.
        #
        # The LLM does NOT pretend to execute the task.
        # task_executor is responsible for calling the
        # actual Brightpeak MCP/tool layer.
        # ----------------------------------------------------

        try:
            raw_result = task_executor(task)

        except Exception as exc:
            # Turn execution failure into an observation.
            # The next planning step can react to the failure.
            result = (
                f"TOOL_EXECUTION_FAILED: "
                f"{type(exc).__name__}: {exc}"
            )

        else:
            # ------------------------------------------------
            # Normalize MCP/tool output to text.
            # ------------------------------------------------

            if isinstance(raw_result, str):
                result = raw_result.strip()

            elif isinstance(raw_result, dict):
                result = str(raw_result)

            else:
                result = str(raw_result)

            if not result.strip():
                result = "TOOL_RETURNED_EMPTY_RESULT"

        # ----------------------------------------------------
        # Save observation.
        #
        # The NEXT planning decision will see this result.
        # This is what makes the decomposition dynamic.
        # ----------------------------------------------------

        history.append(
            (
                task,
                result,
            )
        )

    return history