from urllib.parse import urlparse
import httpx
from markdownify import markdownify as md
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

class WebFetchMdParams(BaseModel):
    url: str = Field(..., description="URL to fetch (must be http:// or https://)")
    timeout: int = Field(
        30,
        ge=5,
        le=120,
        description="Request timeout in seconds (default: 30)",
    )

class WebFetchMdTool(Tool):
    name = "web_fetch_md"
    description = "Fetch content from a URL and convert the HTML to clean Markdown. Useful for reading web pages and documentation."
    kind = ToolKind.NETWORK
    schema = WebFetchMdParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WebFetchMdParams(**invocation.params)

        parsed = urlparse(params.url)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            return ToolResult.error_result(f"Url must be http:// or https://")

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(params.timeout),
                follow_redirects=True,
            ) as client:
                response = await client.get(params.url)
                response.raise_for_status()
                text = response.text
        except httpx.HTTPStatusError as e:
            return ToolResult.error_result(
                f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
            )
        except Exception as e:
            return ToolResult.error_result(f"Request failed: {e}")

        try:
            markdown_text = md(text, heading_style="ATX", escape_asterisks=False, escape_underscores=False).strip()
        except Exception as e:
             return ToolResult.error_result(f"Markdown conversion failed: {e}")

        if len(markdown_text) > 200 * 1024:
            markdown_text = markdown_text[: 200 * 1024] + "\n... [content truncated]"

        return ToolResult.success_result(
            markdown_text,
            metadata={
                "status_code": response.status_code,
                "content_length": len(response.content),
                "markdown_length": len(markdown_text)
            },
        )
