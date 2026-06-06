"""Save a report to the project's reports/ directory.

Separate from write_file so reports always land in a predictable location
regardless of the current run_dir.
"""

from __future__ import annotations

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
        "export, or download something."
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Output filename including extension (e.g. 'AAPL_analysis.md', 'backtest_report.json')",
            },
            "content": {
                "type": "string",
                "description": "Report content to write to the file.",
            },
        },
        "required": ["filename", "content"],
    }
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        filename = kwargs["filename"]
        content = kwargs["content"]

        reports_dir = get_reports_dir()
        # Sanitize: strip path components, keep only the filename
        safe_name = filename.replace("/", "_").replace("\\", "_").lstrip(".")
        if not safe_name:
            safe_name = "report.md"

        path = reports_dir / safe_name
        path.write_text(content, encoding="utf-8")
        return f"Report saved to {path}"
