"""业务层（business）异常打标：把 handle 层的语义失败挂上业务上下文。

架构定位：异常流的第 ③ 层——**透传 + 打标层**。

职责边界（严格遵守「异常链恒为 2 层」约束）：
1. `FrameworkError`（`ElementNotFoundError` / `ConfigError` 等）已自带技术证据，
   此处**裸重抛**，不套第二层链，避免链深度随业务层数膨胀；
2. `AssertionError`（handle 层「业务期望未达成」的结论）无业务归属，
   此处包装为 `BusinessError` 并用 `from` 挂链，补上「场景码 + 步骤名 + 入参」；
3. 其余异常（如 pytest 控制流）一律原样透传。

场景码由调用栈自动推断（`run_e01_xxx` → `E01`），不要求调用方手写，
因此业务代码只需把 `allure_compat.step(...)` 换成 `biz_step(...)`。
"""
from __future__ import annotations

import contextlib
import re
import sys
from typing import Any, Iterator

from common.exceptions import BusinessError, FrameworkError
from util import allure_compat

# run_e01_encrypted_login -> E01 / run_i17_parent_child_amount -> I17
# 注意末尾不能加 \b：场景码后紧跟的是 "_"（同属词字符），\b 不成立会导致永不匹配
_SCENARIO_RE = re.compile(r"^run_([a-zA-Z])(\d{2,3})")

_UNKNOWN_SCENARIO = "UNKNOWN"


def infer_scenario(depth_limit: int = 12) -> str:
    """从调用栈向上找形如 run_xxx 的 business 方法名，推断场景码。

    拿不到（如在非 business 上下文里调用）时返回 "UNKNOWN"，
    绝不因为打标失败而影响原始异常。
    """
    try:
        frame = sys._getframe(1)
    except (AttributeError, ValueError):  # pragma: no cover - 非 CPython
        return _UNKNOWN_SCENARIO

    for _ in range(depth_limit):
        if frame is None:
            break
        matched = _SCENARIO_RE.match(frame.f_code.co_name)
        if matched:
            return f"{matched.group(1).upper()}{matched.group(2)}"
        frame = frame.f_back
    return _UNKNOWN_SCENARIO


@contextlib.contextmanager
def biz_step(title: str, **context: Any) -> Iterator[None]:
    """业务步骤上下文：等价于 allure step，但在异常抛出时自动打上业务标签。

    用法与 `allure_compat.step` 完全一致，额外支持传入业务上下文：
        with biz_step("申请查看客户 C-2001 的敏感字段", cust_id=2001):
            ...
    """
    scenario = infer_scenario()
    with allure_compat.step(title):
        try:
            yield
        except FrameworkError:
            # 已带技术证据的领域异常：原样透传，链深度不变
            raise
        except AssertionError as exc:
            # handle 层的业务结论：补业务归属后重抛（唯一一处套链）
            raise BusinessError(
                f"[{scenario}] 步骤「{title}」未达成: {exc}",
                business_context={"scenario": scenario, "step": title, **context},
            ) from exc
