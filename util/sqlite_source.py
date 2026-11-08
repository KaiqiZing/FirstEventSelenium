# coding=utf-8
"""被测系统 SQLite 落库直读（I-18：页面数字 与 数据库 一致性核对）。

被测系统把结算数据**真实落盘**到 SQLite（`backend/data/settlement.db`），特征如下，
均为金融系统常见现状，需由自动化脚本自行消化：

1. 金额一律以「分」(INTEGER) 落库，页面按「元」展示 —— 单位不一致；
2. `settle_bill.total_amount_cents` 是独立汇总字段，与 `settle_detail` 求和可能漂移；
3. 未清算明细 `amount_cents` 为 NULL，页面展示为「—」；
4. 库文件路径不写死：由被测接口 `/api/dbconsistency/db/meta` 返回。

E-03 密文库（`backend/data/crypto_vault.db` 的 `cust_profile`）同样落盘，
敏感字段一律为 AES-256-GCM 密文（base64）+ 随机 IV，另建 HMAC 摘要列用于等值检索；
库路径由被测接口 `/api/crypto/vault/db/meta` 返回。

本模块只做「读」，返回原始行 dict（金额保持「分」、NULL 保持 None、密文保持原样）。
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any

# 允许直查的表及其主键列（避免拼接 SQL 的注入面）
_TABLES: dict[str, str] = {
    "settle_bill": "bill_no",
    "settle_detail": "bill_no",
    "fund_account": "account_no",
    # E-03 密文库：客户档案（敏感字段为密文，明文需解密后比对）
    "cust_profile": "cust_no",
}


class SqliteSource:
    """SQLite 只读数据源：按表返回原始行，金额单位为「分」。"""

    def __init__(self, db_path: str, timeout: int = 10):
        self.db_path = db_path
        self.timeout = timeout
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"❌ 被测 SQLite 库文件不存在: {db_path}")

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"SqliteSource({self.db_path})"

    # ---------------- 原始行查询 ---------------- #
    def rows(self, table: str, key: str | None = None) -> list[dict[str, Any]]:
        """查询整表（`key` 为主键值时按主键过滤）。

        :param table: settle_bill / settle_detail / fund_account / cust_profile
        :param key: 主键值（账单号 / 资金账号 / 客户号），为空则返回全表
        """
        column = _TABLES.get(table)
        if not column:
            raise ValueError(f"❌ 不支持直查的表: {table}，可选: {sorted(_TABLES)}")
        sql = f"SELECT * FROM {table}"
        params: tuple = ()
        if key is not None:
            sql += f" WHERE {column} = ?"
            params = (key,)
        return self._query(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """自定义只读 SQL（仅限 SELECT）。"""
        if not sql.lstrip().lower().startswith("select"):
            raise ValueError("❌ SqliteSource 仅允许执行 SELECT 查询")
        return self._query(sql, params)

    def _query(self, sql: str, params: tuple) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
