"""
Validation schema for the Constrained ReAct agent.

Every single response from the model MUST conform to this schema.
If it doesn't (missing field, wrong type, invalid JSON), Pydantic raises
a ValidationError and the agent treats that step as a failure rather than
silently accepting malformed output.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class AgentResponse(BaseModel):
    thought: str = Field(..., description="The agent's reasoning about what to do next.")
    action: Literal["use_tool", "final_answer"] = Field(
        ..., description="Whether the agent wants to call a tool or give its final answer."
    )
    tool: Optional[str] = Field(
        None, description="Name of the tool to call. Required when action is 'use_tool'."
    )
    tool_input: Optional[str] = Field(
        None, description="Input string passed to the tool. Required when action is 'use_tool'."
    )
    final_answer: Optional[str] = Field(
        None, description="The recommendation and explanation. Required when action is 'final_answer'."
    )

    @model_validator(mode="after")
    def check_action_consistency(self):
        if self.action == "use_tool":
            if not self.tool or not self.tool_input:
                raise ValueError("'tool' and 'tool_input' are required when action is 'use_tool'.")
            if self.final_answer:
                raise ValueError("'final_answer' must be null when action is 'use_tool'.")
        elif self.action == "final_answer":
            if not self.final_answer:
                raise ValueError("'final_answer' is required when action is 'final_answer'.")
            if self.tool or self.tool_input:
                raise ValueError("'tool' and 'tool_input' must be null when action is 'final_answer'.")
        return self
