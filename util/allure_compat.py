"""Allure 兼容层：allure 未安装时降级为无操作，保证用例仍可执行。

安装 allure-pytest 后自动使用真实 allure（step/feature/story/dynamic.title）。

所有 attach_* 遵循同一原则：**取证失败绝不掩盖原始失败**，
故附件写入一律兜底为日志，永不向调用方抛异常。
"""
from __future__ import annotations

from log.user_log import get_logger

logger = get_logger()

try:  # pragma: no cover - 依赖探测
    import allure  # type: ignore

    HAS_ALLURE = True
    step = allure.step
    feature = allure.feature
    story = allure.story

    def dynamic_title(title: str) -> None:  # pragma: no cover
        allure.dynamic.title(title)

except Exception:  # pragma: no cover - 降级
    HAS_ALLURE = False

    import contextlib

    @contextlib.contextmanager
    def step(title: str):
        logger.info("STEP: %s", title)
        yield

    def _passthrough(*args, **kwargs):
        def wrapper(fn):
            return fn
        return wrapper

    feature = _passthrough
    story = _passthrough

    def dynamic_title(title: str) -> None:  # pragma: no cover
        logger.info("TITLE: %s", title)


def attach_text(name: str, body: str) -> None:
    """把文本附件写入 allure（不可用时仅打日志）。"""
    if HAS_ALLURE:  # pragma: no cover
        try:
            allure.attach(body, name=name, attachment_type=allure.attachment_type.TEXT)
            return
        except Exception as exc:
            logger.warning("文本附件写入 allure 失败: %s", exc)
    logger.info("[attach] %s: %s", name, body)


def attach_png(name: str, path: str) -> None:
    """把 PNG 截图写入 allure（不可用时仅打日志）。

    失败现场截图只有进入报告才能形成闭环证据链，否则仅落盘在
    logs/screenshots 下，排查时还得按路径手动翻找。
    """
    if HAS_ALLURE:  # pragma: no cover
        try:
            allure.attach.file(path, name=name, attachment_type=allure.attachment_type.PNG)
            return
        except Exception as exc:
            logger.warning("截图附件写入 allure 失败(%s): %s", path, exc)
    logger.info("[attach-png] %s: %s", name, path)
