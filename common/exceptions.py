"""项目通用异常定义与异常链格式化。"""
from __future__ import annotations

from typing import Any, Optional


class FrameworkError(Exception):
    """框架基础异常，统一保留 message 与结构化证据。

    子类只需覆写 evidence()，__str__ 与失败报告导出即自动同步，
    避免「新增了证据字段却忘了让它出现在失败信息里」。

    证据载体分两种用途：
    - __str__/evidence()：单行可读（适配 --tb=line 等精简模式）；
    - format_exception_chain()：多层可读（供报告归档）。
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def evidence(self) -> dict[str, Any]:
        """结构化证据（供失败报告提取），子类按需覆写。"""
        return {}

    def __str__(self) -> str:
        parts = [self.message]
        parts.extend(f"{key}: {value}" for key, value in self.evidence().items() if value)
        return " / ".join(parts)


class ElementNotFoundError(FrameworkError):
    """元素查找失败异常。"""

    def __init__(
        self,
        message: str,
        locator: Optional[Any] = None,
        screenshot_path: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.locator = locator
        self.screenshot_path = screenshot_path

    def evidence(self) -> dict[str, Any]:
        return {"定位器": self.locator, "截图": self.screenshot_path}


class BusinessError(FrameworkError):
    """业务流程执行失败异常。"""

    def __init__(self, message: str, business_context: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.business_context = business_context or {}

    def evidence(self) -> dict[str, Any]:
        return {"上下文": self.business_context}


class ConfigError(FrameworkError):
    """配置读取/解析失败异常。"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.config_key = config_key
        self.config_file = config_file

    def evidence(self) -> dict[str, Any]:
        return {"配置键": self.config_key, "配置文件": self.config_file}


def format_exception_chain(exc: BaseException, max_depth: int = 6) -> str:
    """沿 __cause__ / __context__ 把异常链展开为可读文本（供失败报告归档）。

    按「最外层 → 根因」排列并标出层间关系，关系直接对应源码写法：
        [1/2] 最外层（用例直接看到）  BusinessError: ... / 上下文: {...}
        [2/2] raise ... from 的直接原因  AssertionError: 公钥在 15s 内未签发完成...
    本工程要求异常链恒为 2 层（技术根因 → 领域异常）；
    若报告中链深度 > 2，说明某层做了多余翻译，应回退该层。
    """
    nodes: list[tuple[BaseException, str]] = []
    seen: set[int] = set()
    current: Optional[BaseException] = exc

    while current is not None and len(nodes) < max_depth and id(current) not in seen:
        seen.add(id(current))
        cause = current.__cause__
        context = current.__context__
        nodes.append((current, "from" if cause is not None else "during"))
        current = cause if cause is not None else context

    total = len(nodes)
    lines: list[str] = []
    for index, (node, _relation) in enumerate(nodes):
        if index == 0:
            role = "最外层（用例直接看到）"
        elif nodes[index - 1][1] == "from":
            role = "raise ... from 的直接原因"
        else:
            role = "处理上一异常时发生"
        lines.append(f"[{index + 1}/{total}] {role}  {type(node).__name__}: {node}")
    return "\n".join(lines)


def find_in_chain(exc: BaseException | None, attr: str, max_depth: int = 6) -> Any:
    """沿异常链查找第一个带指定属性的异常（如 screenshot_path / locator）。

    用于收敛层取证：最外层异常未必直接持有截图（例如业务层打标后的
    BusinessError），但根因里往往挂着 ElementNotFoundError。
    """
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    depth = 0
    while current is not None and depth < max_depth and id(current) not in seen:
        seen.add(id(current))
        value = getattr(current, attr, None)
        if value:
            return value
        current = current.__cause__ or current.__context__
        depth += 1
    return None
