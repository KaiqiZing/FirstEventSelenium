"""浏览器真实网络层记录（CDP Network 域）：抓取 DevTools Network 面板等价数据。

背景：页面 DOM 上的报文区（如 E-01 的 `#request-body`）与摘要区都是**前端自证**，
前端伪造一份假密文照样能显示。本模块取的是浏览器网络栈真实收发的请求体与
响应体，等同于在 DevTools 的 Network 面板里看 Payload / Response 两栏。

能力边界（务必遵守）：
1. 仅 Chromium 内核（chrome / chromium / edge）支持 CDP；Firefox / Safari 下
   `supported` 为 False，`start()` 返回 False，用例须用 `try_wait_record` 的
   返回值做判空并跳过网络层断言，改由接口层（ApiClient）兜底；
2. 只解决「证据来源可信」，**不解决「期望值可信」**：从网络层取回的摘要仍须与
   脚本独立复算（util/digest_util）的结果比对，不能因为"是网络层拿到的"就直接采信；
3. 网络层断言一律是**增强项**，不能成为场景的唯一断言源，否则换浏览器即失败。

迁移提示：用例只依赖本类的公开方法，不直接触碰 `execute_cdp_cmd`。将来若切换到
Selenium BiDi 或 Playwright，只需替换本文件的后端实现，用例无需改动。

前置：driver 必须开启 performance 日志（见 DriverFactory._enable_performance_log），
否则 `get_log("performance")` 恒为空，一条记录都抓不到（此时会降级而非报错）。
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any

from log.user_log import get_logger


class NetworkRecorder:
    """按 URL 抓取浏览器真实收发的请求体 / 响应体。

    典型用法（请统一用 `get_network_recorder(driver)` 取实例）：:

        rec = get_network_recorder(driver)
        rec.start()                       # 必须在目标请求发出之前调用
        ...                               # 页面操作
        wire = rec.try_wait_record("/api/crypto/login/encrypted")
        if wire:                          # 抓不到就跳过，不阻断用例
            req = wire["req_json"]        # 真实请求体
            resp = wire["resp_json"]      # 真实响应体
        rec.stop()
    """

    def __init__(self, driver, timeout: int = 10):
        self.driver = driver
        self.timeout = timeout
        self.logger = get_logger()
        self._enabled = False
        self._log_warned = False
        self._by_id: dict[str, dict[str, Any]] = {}

    # ---------------- 生命周期 ---------------- #
    @property
    def supported(self) -> bool:
        """CDP 仅 Chromium 内核可用；Firefox / Safari 返回 False。"""
        return hasattr(self.driver, "execute_cdp_cmd")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> bool:
        """开启 Network 域并清空历史记录，返回是否可用。

        必须在目标请求发出**之前**调用：requestId 只在 enable 之后有效，
        事后再开启拿不到响应体。
        """
        if not self.supported:
            self.logger.warning("当前浏览器不支持 CDP，跳过网络层记录（回退接口层断言）")
            return False
        try:
            self.driver.execute_cdp_cmd("Network.enable", {})
        except Exception as exc:  # 驱动被关闭 / 内核版本不支持
            self.logger.warning("Network 域开启失败，跳过网络层记录: %s", exc)
            return False
        self._by_id.clear()
        self._enabled = True
        return True

    def stop(self) -> None:
        """关闭 Network 域：session 级 driver 跨用例复用，不关会持续缓存响应体。"""
        if not self._enabled:
            return
        try:
            self.driver.execute_cdp_cmd("Network.disable", {})
        except Exception as exc:
            self.logger.debug("Network 域关闭失败（driver 可能已退出）: %s", exc)
        self._enabled = False

    def clear(self) -> None:
        """清空已捕获记录（同一用例内分阶段比对时使用）。"""
        if self._enabled:
            self.drain()  # 先排空缓冲，避免残留事件在 clear 之后被写回
        self._by_id.clear()

    # ---------------- 采集 ---------------- #
    def drain(self) -> None:
        """取回 performance 日志缓冲。

        注意：`get_log` 会**清空**浏览器侧缓冲，因此每次都必须全量取走，
        不能分多次部分读取。
        """
        if not self._enabled:
            return
        try:
            entries = self.driver.get_log("performance")
        except Exception as exc:
            # 只告警一次：后续每次取数都刷屏会把真正有用的失败信息淹掉
            self._enabled = False
            if not self._log_warned:
                self._log_warned = True
                self.logger.warning(
                    "读取 performance 日志失败，网络层断言整体跳过: %s；"
                    "如需关闭该能力可设 UIEVENT_DISABLE_PERF_LOG=1", exc)
            return
        for entry in entries:
            try:
                msg = json.loads(entry["message"]).get("message", {})
            except (ValueError, TypeError, KeyError):
                continue
            method, params = msg.get("method"), msg.get("params") or {}
            rid = params.get("requestId")
            if method == "Network.requestWillBeSent":
                req = params.get("request") or {}
                self._by_id[rid] = {
                    "requestId": rid,
                    "url": req.get("url", ""),
                    "method": req.get("method", ""),
                    "postData": req.get("postData"),
                }
            elif method == "Network.responseReceived":
                resp = params.get("response") or {}
                item = self._by_id.setdefault(rid, {"requestId": rid, "url": ""})
                item.update({
                    "url": resp.get("url") or item.get("url", ""),
                    "status": resp.get("status"),
                    "mimeType": resp.get("mimeType"),
                })
            elif method == "Network.loadingFinished":
                self._by_id.setdefault(rid, {"requestId": rid, "url": ""})["finished"] = True

    def _fetch_bodies(self, items: list[dict[str, Any]] | None = None) -> None:
        """补齐已完成请求的响应体（重定向 / 204 / 流式响应取不到，置 None）。

        只处理传入的条目：页面动辄上百个静态资源请求，逐条 `getResponseBody`
        会让每次取数慢上数秒。
        """
        targets = self._by_id.values() if items is None else items
        for item in targets:
            if not item.get("finished") or "body" in item:
                continue
            try:
                res = self.driver.execute_cdp_cmd(
                    "Network.getResponseBody", {"requestId": item["requestId"]})
            except Exception as exc:
                item["body"] = None
                self.logger.debug("响应体不可读 %s: %s", item.get("url"), exc)
                continue
            item["body"] = self._decode(res.get("body"), res.get("base64Encoded", False))

    @staticmethod
    def _decode(body: str | None, base64_encoded: bool) -> str | None:
        if body is None:
            return None
        if not base64_encoded:
            return body
        try:
            return base64.b64decode(body).decode("utf-8", "replace")
        except Exception:
            return None

    @staticmethod
    def _safe_json(raw: str | None) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    # ---------------- 取数 ---------------- #
    def records(self, url_contains: str) -> list[dict[str, Any]]:
        """返回 URL 命中的全部记录，按请求发起顺序排列。

        每条记录含：url / method / status / postData / body / req_json / resp_json。
        URL 用 contains 匹配：前后端经 Vite 代理同源，且端口存在回退探测。
        """
        self.drain()
        items = [v for v in self._by_id.values() if url_contains in (v.get("url") or "")]
        self._fetch_bodies(items)
        for item in items:
            item["req_json"] = self._safe_json(item.get("postData"))
            item["resp_json"] = self._safe_json(item.get("body"))
        return items

    def wait_record(self, url_contains: str, timeout: int | None = None) -> dict[str, Any]:
        """等待命中 URL 的**第一条**记录；超时抛 AssertionError（严格模式）。

        能力不可用时立即失败而非空转轮询：降级路径下每次等满 timeout 会显著拖慢用例。
        """
        if not self._enabled:
            raise AssertionError("网络层记录不可用（非 Chromium 内核或 performance 日志未开启）")
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            items = self.records(url_contains)
            if items:
                return items[0]
            time.sleep(0.2)
        raise AssertionError(f"未在 {timeout or self.timeout}s 内捕获请求: {url_contains}")

    def try_wait_record(self, url_contains: str, timeout: int | None = None) -> dict[str, Any] | None:
        """降级版：抓不到只告警并返回 None，不阻断用例。

        用于「网络层断言是增强项」的场景 —— Firefox 无 CDP、或 performance 日志
        未开启时，场景仍要能靠接口层断言跑通。
        """
        try:
            return self.wait_record(url_contains, timeout)
        except AssertionError as exc:
            # 能力不可用时 drain() 已告警过，这里不再重复刷屏
            if self._enabled:
                self.logger.warning("未捕获到网络请求，跳过网络层断言: %s", exc)
            return None

    def last_record(self, url_contains: str) -> dict[str, Any] | None:
        """命中 URL 的最后一条记录（重复提交场景取最新一次）。"""
        items = self.records(url_contains)
        return items[-1] if items else None


#: 按 driver 复用同一实例。业务层会反复 `new Handle`，若各自持有 NetworkRecorder，
#: 会出现「A 实例 start、B 实例取数恒为空」的陷阱（_enabled 是实例级标志）。
_CACHE: dict[int, NetworkRecorder] = {}


def get_network_recorder(driver) -> NetworkRecorder:
    """取与 driver 绑定的共享记录器（同一 driver 只开一次 Network 域）。"""
    key = id(driver)
    rec = _CACHE.get(key)
    if rec is None or rec.driver is not driver:
        rec = NetworkRecorder(driver)
        _CACHE[key] = rec
    return rec
