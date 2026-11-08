# coding=utf-8
"""口令摘要复算工具（E-01 传输字段加密）。

被测系统改造后，加密提交的日志与响应体**不再回显明文口令**（生产系统本就不该
回显），改为回传服务端解密结果的摘要 `serverDigest`，由前端用 Web Crypto 对输入
明文算出 `localDigest` 后比对。由此带来 E-01 的口径变化：

1. 稳定断言点从「明文相等」改为「摘要相等」：SHA-256 截断 16 个 hex 字符
   （64 bit），碰撞概率可忽略，对测试验证与明文等价；
2. 脚本用 `hashlib` **独立复算**，不依赖浏览器的 Web Crypto：
   - 既能与页面 `#local-digest` 互校，证伪前端摘要实现错误；
   - 也能在非安全上下文（无 `crypto.subtle`、页面显示「未比对」）下继续验证。

⚠️ 算法规范必须与被测系统一致：`SHA-256(明文 UTF-8) → hex → 取前 16 位 → 大写`。
   若被测系统后续加入 salt / 归一化（trim、大小写折叠），需同步修改本模块。
"""
from __future__ import annotations

import hashlib

# 摘要长度（hex 字符数）：被测系统取 SHA-256 前 16 位大写
DIGEST_LENGTH = 16


def password_digest(plain: str, length: int = DIGEST_LENGTH) -> str:
    """按被测系统约定复算明文摘要：SHA-256 → hex → 前 N 位 → 大写。"""
    digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return digest[:length].upper()


def digest_equal(actual: str, expected_plain: str) -> bool:
    """实际摘要 == 明文的期望摘要（页面取文本常带空白，故先 strip + 统一大写）。"""
    return (actual or "").strip().upper() == password_digest(expected_plain)
