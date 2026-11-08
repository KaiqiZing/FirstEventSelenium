"""统一截图工具。"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from config.settings import Config


class ScreenshotUtil:
    """统一管理页面/元素截图路径与命名。"""

    BASE_DIR = Path(__file__).resolve().parent.parent

    @classmethod
    def _ensure_dir(cls) -> Path:
        configured_path = Config().get("screenshot.path", "logs/screenshots")
        screenshot_dir = cls.BASE_DIR / configured_path
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        return screenshot_dir

    @staticmethod
    def sanitize_name(name: str) -> str:
        cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(name).strip())
        return cleaned.strip("._") or "screenshot"

    @classmethod
    def _build_path(cls, case_id: str, prefix: str) -> str:
        safe_case_id = cls.sanitize_name(case_id)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = cls._ensure_dir() / f"{prefix}_{safe_case_id}_{timestamp}.png"
        return str(target)

    @classmethod
    def capture(cls, driver: Any, case_id: str) -> str:
        screenshot_path = cls._build_path(case_id, "page")
        driver.save_screenshot(screenshot_path)
        return screenshot_path

    @classmethod
    def capture_element(cls, driver: Any, element: Any, case_id: str) -> str:
        screenshot_path = cls._build_path(case_id, "element")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        except Exception:
            pass
        element.screenshot(screenshot_path)
        return screenshot_path
