"""Save a report to the project's reports/ directory.

Separate from write_file so reports always land in a predictable location
regardless of the current run_dir.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.agent.tools import BaseTool
from src.config.paths import get_reports_dir


class SaveReportTool(BaseTool):
    """Write a report file to the project reports directory."""

    name = "save_report"

    @classmethod
    def check_available(cls) -> bool:
        return True

    description = (
        "Save a report, analysis, or any text content to the project's "
        "reports/ directory. Use this whenever the user asks to save, "
        "export, or download something. The file is automatically named "
        "with a timestamp prefix; provide a short descriptive topic only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Short descriptive name for the report (e.g. 'AAPL_analysis', 'portfolio_review'). The tool auto-prepends a timestamp.",
            },
            "content": {
                "type": "string",
                "description": "Report content to write to the file.",
            },
        },
        "required": ["topic", "content"],
    }
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        topic = kwargs["topic"]
        content = kwargs["content"]

        # Auto-prefix with timestamp for consistent chronological sorting
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        safe = topic.replace("/", "_").replace("\\", "_").replace(" ", "_").lstrip("._-")
        if not safe:
            safe = "report"
        filename = f"{ts}_{safe}.md"

        path = get_reports_dir() / filename
        path.write_text(content, encoding="utf-8")
        return f"Report saved to {path}"
