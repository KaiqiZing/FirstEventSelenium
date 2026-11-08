# coding=utf-8
"""金融金额文本解析与容差比较工具。

被测页面金额统一按 `¥1,286,500.00` 格式化展示，负数用括号表示 `(¥3,400.00)`，
且单元格文案常带前缀（如「子单合计 ¥510,711.00」「差异 ¥0.01」）。

金额断言必须先把文本清洗成 `Decimal` 再用容差比较：
- 禁止 `float` 直接相等（浮点求和会产生 0.0000000x 尾差）；
- 括号、千分位、货币符号必须在断言前剥离。
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# 从任意文案中抽取数值部分：¥1,286,500.00 / (¥3,400.00) / -¥12.00 / 差异 ¥0.01
_AMOUNT_PATTERN = re.compile(r"\(?\s*([-+]?)\s*[¥￥]?\s*(\d[\d,]*(?:\.\d+)?)\s*\)?")

# 金融金额比较容差：一分钱以内视为一致（规避浮点尾差）
DEFAULT_TOLERANCE = Decimal("0.005")


def parse_amount(text: str) -> Decimal:
    """把页面金额文本解析为 Decimal，括号包裹视为负数。

    >>> parse_amount("¥1,286,500.00")
    Decimal('1286500.00')
    >>> parse_amount("(¥3,400.00)")
    Decimal('-3400.00')
    >>> parse_amount("子单合计 ¥510,711.00")
    Decimal('510711.00')
    """
    raw = (text or "").strip()
    match = _AMOUNT_PATTERN.search(raw)
    if not match:
        raise ValueError(f"无法从文本中解析金额: {text!r}")
    try:
        value = Decimal(match.group(2).replace(",", ""))
    except InvalidOperation as exc:  # pragma: no cover - 正则已保证为数字
        raise ValueError(f"无法从文本中解析金额: {text!r}") from exc
    negative = match.group(1) == "-" or (raw.startswith("(") and raw.endswith(")"))
    return -value if negative else value


def amount_equal(actual, expected, tolerance=DEFAULT_TOLERANCE) -> bool:
    """金额容差比较（默认 0.005，即一分钱以内视为一致）。"""
    diff = Decimal(str(actual)) - Decimal(str(expected))
    return abs(diff) <= Decimal(str(tolerance))


def cents_to_yuan(cents) -> Decimal | None:
    """「分」转「元」：数据库侧金额一律为整数分，页面按元展示，断言前需统一单位。

    None 原样返回，代表库中未落金额（未清算明细），与「0 元」含义不同。

    >>> cents_to_yuan(86230000)
    Decimal('862300.00')
    >>> cents_to_yuan(None) is None
    True
    """
    if cents is None:
        return None
    return (Decimal(int(cents)) / Decimal(100)).quantize(Decimal("0.01"))
