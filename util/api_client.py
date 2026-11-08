"""被测系统后端接口客户端（requests.Session 封装）。

统一响应约定: {"code": 0|非0, "data": ..., "message": "..."}，code=0 成功。
被测系统数据全部为后端内存态，重启即复位。
"""
from __future__ import annotations

from typing import Any

import requests

from config.settings import Config
from log.user_log import get_logger


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: int = 10):
        env_config = Config().get_env_config()
        self.base_url = (base_url or str(env_config.get("api_base_url", "http://127.0.0.1:5000"))).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.logger = get_logger()

    # ---------- 通用请求 ----------
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"code": 0, "data": response.content, "message": "ok"}

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("POST", path, **kwargs)

    # ---------- 业务接口 ----------
    def health(self) -> dict[str, Any]:
        return self.get("/api/health")

    def captcha_new(self) -> dict[str, Any]:
        """GET /api/captcha：返回 {code, data:{sid, image(b64)}} 或类似。"""
        return self.get("/api/captcha")

    def captcha_verify(self, sid: str, code: str) -> dict[str, Any]:
        return self.post("/api/captcha/verify", json={"sid": sid, "code": code})

    def export_start(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.post("/api/export/start", json=payload or {})

    def export_status(self, task_id: str) -> dict[str, Any]:
        return self.get(f"/api/export/status/{task_id}")

    def export_file(self, task_id: str) -> bytes:
        url = f"{self.base_url}/api/export/file/{task_id}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def race_save(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/api/race/save", json=payload)

    def race_list(self) -> dict[str, Any]:
        return self.get("/api/race/list")

    def seed_new(self) -> dict[str, Any]:
        return self.post("/api/seed/new")

    def seed_list(self) -> dict[str, Any]:
        return self.get("/api/seed/list")

    def auth_login(self, username: str, password: str, remember: bool = False) -> dict[str, Any]:
        return self.post("/api/auth/login", json={"username": username, "password": password, "remember": remember})

    def auth_me(self) -> dict[str, Any]:
        return self.get("/api/auth/me")

    def auth_logout(self) -> dict[str, Any]:
        return self.post("/api/auth/logout")

    def slow_items(self, delay: int = 3) -> dict[str, Any]:
        return self.get(f"/api/slow/items?delay={delay}")

    def unstable(self) -> dict[str, Any]:
        return self.get("/api/unstable")

    def items_page(self, page: int = 1, size: int = 10) -> dict[str, Any]:
        return self.get(f"/api/items?page={page}&size={size}")

    # ---------- I-18 页面数字 与 数据库 一致性核对 ----------
    def dbconsistency_page(self, page: int = 1, size: int = 5) -> dict[str, Any]:
        """页面数据源：明细分页 + 汇总卡片（汇总卡片取的是结算单汇总字段合计）。"""
        return self.get(f"/api/dbconsistency/page?page={page}&size={size}")

    def dbconsistency_meta(self) -> dict[str, Any]:
        """库文件路径与各表行数/最后更新时间。"""
        return self.get("/api/dbconsistency/db/meta")

    def dbconsistency_query(self, target: str, **filters: Any) -> dict[str, Any]:
        """服务端直查库表原始行（金额为「分」，NULL 保留）。"""
        params = {"target": target}
        params.update(filters)
        return self.get("/api/dbconsistency/db/query", params=params)

    def dbconsistency_detail_update(self, detail_id: int, amount) -> dict[str, Any]:
        """改明细金额：只写明细表，不回写结算单汇总字段。"""
        return self.post("/api/dbconsistency/detail/update", json={"id": detail_id, "amount": amount})

    def dbconsistency_bill_recap(self, bill_no: str) -> dict[str, Any]:
        """按明细求和回写结算单汇总字段。"""
        return self.post("/api/dbconsistency/bill/recap", json={"billNo": bill_no})

    def dbconsistency_account_post(self, account_no: str | None = None, delta=None) -> dict[str, Any]:
        """模拟清算入账：直接改库，页面不刷新（制造陈旧读数）。"""
        payload: dict[str, Any] = {}
        if account_no:
            payload["accountNo"] = account_no
        if delta is not None:
            payload["delta"] = delta
        return self.post("/api/dbconsistency/account/post", json=payload)

    def dbconsistency_reset(self) -> dict[str, Any]:
        """重建数据库，恢复初始数据（保证用例可重复执行）。"""
        return self.post("/api/dbconsistency/reset")

    # ---------- E-01~E-04 数据加密场景 ----------
    # 说明：业务失败（1001/1002/1003/2001/2002/2003）HTTP 仍是 200，
    # 统一响应体里带 code，脚本侧按 code 判断，不能只看 raise_for_status。
    def crypto_pubkey(self) -> dict[str, Any]:
        """RSA 公钥：带 0.3~0.8s 随机延迟签发（异步资源，必须等待）。"""
        return self.get("/api/crypto/pubkey")

    def crypto_pubkey_rotate(self) -> dict[str, Any]:
        """轮换密钥对：轮换前用旧公钥加密的密文随即失效（1003）。"""
        return self.post("/api/crypto/pubkey/rotate")

    def crypto_session_key(self) -> dict[str, Any]:
        """会话 AES-256-GCM 密钥（base64），供脚本侧解密。"""
        return self.get("/api/crypto/session-key")

    def crypto_encrypt(self, plain: str, alg: str = "AES-GCM", key_version: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"plain": plain, "alg": alg}
        if key_version:
            payload["keyVersion"] = key_version
        return self.post("/api/crypto/encrypt", json=payload)

    def crypto_decrypt(self, cipher_b64: str, iv_b64: str | None = None,
                       key_version: str | None = None, alg: str = "AES-GCM") -> dict[str, Any]:
        payload: dict[str, Any] = {"cipherB64": cipher_b64, "ivB64": iv_b64, "alg": alg}
        if key_version:
            payload["keyVersion"] = key_version
        return self.post("/api/crypto/decrypt", json=payload)

    def crypto_login_encrypted(self, account: str, credential_b64: str,
                               key_version: str | None = None) -> dict[str, Any]:
        """加密通道登录：默认只回 serverDigest / maskedPassword / decrypted。

        明文口令默认**不回显**；仅当被测系统 `CRYPTO_ECHO_PLAINTEXT=True` 时才额外
        返回 `revealedPassword`（测试环境应为 False，用例会反向断言该字段不存在）。
        """
        payload: dict[str, Any] = {"account": account, "credentialB64": credential_b64}
        if key_version:
            payload["keyVersion"] = key_version
        return self.post("/api/crypto/login/encrypted", json=payload)

    def crypto_login_plain(self, account: str, password: str) -> dict[str, Any]:
        """对照组：明文通道被服务端拒绝（1001）。"""
        return self.post("/api/crypto/login/plain", json={"account": account, "password": password})

    def crypto_masked_customers(self) -> dict[str, Any]:
        return self.get("/api/crypto/masked/customers")

    def crypto_masked_reveal(self, record_id: int) -> dict[str, Any]:
        """单条明文查看：同一条 5 秒冷却（1002）。"""
        return self.post("/api/crypto/masked/reveal", json={"id": record_id})

    def crypto_masked_raw(self) -> dict[str, Any]:
        """服务端全量明文：脱敏断言的稳定数据源。"""
        return self.get("/api/crypto/masked/raw")

    def crypto_vault_page(self, page: int = 1, size: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page}
        if size:
            params["size"] = size
        return self.get("/api/crypto/vault/page", params=params)

    def crypto_vault_db_query(self) -> dict[str, Any]:
        """密文库原始行：只有密文 / IV / 摘要，没有明文。"""
        return self.get("/api/crypto/vault/db/query")

    def crypto_vault_db_meta(self) -> dict[str, Any]:
        return self.get("/api/crypto/vault/db/meta")

    def crypto_vault_decrypt(self, cipher_b64: str, iv_b64: str | None = None,
                             key_version: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"cipherB64": cipher_b64, "ivB64": iv_b64}
        if key_version:
            payload["keyVersion"] = key_version
        return self.post("/api/crypto/vault/decrypt", json=payload)

    def crypto_vault_write(self, cust_no: str | None = None, cust_name: str | None = None,
                           mobile: str | None = None, balance: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"custNo": cust_no, "custName": cust_name,
                                   "mobile": mobile, "balance": balance}
        return self.post("/api/crypto/vault/write",
                         json={k: v for k, v in payload.items() if v is not None})

    def crypto_vault_reset(self) -> dict[str, Any]:
        """重建密文库（进程内密钥随之重生成，跨会话缓存的密文必然失效）。"""
        return self.post("/api/crypto/vault/reset", json={})

    def crypto_envelope(self, mode: str = "normal") -> dict[str, Any]:
        """加密报文：mode ∈ normal / expired / tampered。"""
        return self.get("/api/crypto/envelope", params={"mode": mode})

    def crypto_envelope_verify(self, ts, sign: str, enc_b64: str) -> dict[str, Any]:
        """时间戳（±120s，2001）+ HMAC 签名校验（2002）。"""
        return self.post("/api/crypto/envelope/verify",
                         json={"ts": ts, "sign": sign, "encB64": enc_b64})


_default_client: ApiClient | None = None


def get_client() -> ApiClient:
    global _default_client
    if _default_client is None:
        _default_client = ApiClient()
    return _default_client
