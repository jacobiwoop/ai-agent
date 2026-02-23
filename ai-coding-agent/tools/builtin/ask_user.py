from typing import Any
from pydantic import BaseModel, Field
from config.config import Config
from tools.base import Tool, ToolInvocation, ToolResult


class AskUserParams(BaseModel):
    question: str = Field(
        ..., description="The question or prompt to display to the user."
    )


class AskUserTool(Tool):
    """
    A tool that pauses the agent's execution to ask the user a question and wait for a string response.
    Useful when the agent needs specific information (like a token, a password, or a decision) to proceed.
    """

    name = "ask_user"
    description = "Ask the user a question and wait for their textual response."
    schema = AskUserParams

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return False

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = AskUserParams(**invocation.params)
        
        if not invocation.ask_user_callback:
            return ToolResult.error_result("ask_user is not supported in this environment.")
            
        try:
            answer = await invocation.ask_user_callback(params.question)
            return ToolResult.success_result(answer)
        except Exception as e:
            return ToolResult.error_result(f"Failed to get user input: {e}")
