"""统一 WebDriver 创建入口（含下载目录 prefs 配置）。"""
from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

from common.exceptions import ConfigError
from config.settings import Config
from log.user_log import get_logger

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
except ImportError:  # pragma: no cover
    ChromeDriverManager = None
    GeckoDriverManager = None
    EdgeChromiumDriverManager = None


class DriverFactory:
    logger = get_logger()

    #: 国产/衍生 Chromium 内核浏览器类型别名 -> 统一归一化到 chromium 分支。
    BROWSER_ALIASES = {
        "360": "chromium",
        "360se": "chromium",
        "360chrome": "chromium",
        "qq": "chromium",
        "qqbrowser": "chromium",
    }

    @staticmethod
    def _project_dir() -> Path:
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def _resolve_download_dir() -> str | None:
        cfg = Config()
        raw = cfg.get("browser.download_dir", "downloads")
        if not raw:
            return None
        path = DriverFactory._project_dir() / str(raw).strip()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @staticmethod
    def _build_common_options(options: Any, headless: bool) -> Any:
        # --disable-gpu：各平台通用，保留。
        options.add_argument("--disable-gpu")
        # --no-sandbox / --disable-dev-shm-usage 仅 Linux（CI/Docker 沙箱）需要；
        # Windows/macOS 下无必要，去掉可让启动参数更干净并规避个别安全软件误判。
        if platform.system() == "Linux":
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        download_dir = DriverFactory._resolve_download_dir()
        if download_dir:
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            options.add_experimental_option("prefs", prefs)
        DriverFactory._enable_performance_log(options)
        if headless:
            options.add_argument("--headless=new")
        return options

    @staticmethod
    def _enable_performance_log(options: Any) -> None:
        """开启 performance 日志：网络层断言（util/network_recorder）的前置条件。

        不开这个，`driver.get_log("performance")` 恒为空，Network 域事件一条都收不到；
        此时 NetworkRecorder 会降级跳过，用例不会失败，但网络层断言全部静默失效。
        Chromium 用 `goog:loggingPrefs`；Edge 追加 `ms:loggingPrefs`（两者都设以兼容）。

        副作用：浏览器中会持续累积 performance 日志缓冲，只有被 `get_log` 取走才释放。
        长时间/大流量场景下若怀疑由此引发驱动不稳，可用环境变量一键关闭：
        `UIEVENT_DISABLE_PERF_LOG=1`（关闭后网络层断言自动降级，不影响用例通过）。
        """
        if os.environ.get("UIEVENT_DISABLE_PERF_LOG"):
            DriverFactory.logger.warning("已按 UIEVENT_DISABLE_PERF_LOG 关闭 performance 日志")
            return
        keys = ["goog:loggingPrefs"]
        if isinstance(options, EdgeOptions):
            keys.insert(0, "ms:loggingPrefs")
        for key in keys:
            options.set_capability(key, {"performance": "ALL"})
        options.add_experimental_option(
            "perfLoggingPrefs", {"enableNetwork": True, "enablePage": False})

    @staticmethod
    def _pick_driver_path(browser_cfg: dict, legacy_key: str) -> str | None:
        """优先顶层 driver_path，其次兼容历史 key（如 browser.chrome_driver_path）。"""
        for key in ("driver_path", legacy_key):
            raw = browser_cfg.get(key, "")
            if raw and str(raw).strip():
                return str(raw).strip()
        return None

    @staticmethod
    def _apply_chromium_binary(options: Any, browser_cfg: dict) -> None:
        """Chromium 内核可指定 binary_location，用于 360/QQ 等国产浏览器指向其可执行文件。"""
        raw = browser_cfg.get("binary_path", "")
        if raw and str(raw).strip():
            options.binary_location = str(raw).strip()
            DriverFactory.logger.info("Chromium binary_location: %s", options.binary_location)

    @staticmethod
    def _launch_chromium(headless: bool, browser_cfg: dict):
        """Chromium 内核（chrome/chromium）真实创建：binary_location + driver_path/manager 兜底。"""
        options = DriverFactory._build_common_options(ChromeOptions(), headless)
        DriverFactory._apply_chromium_binary(options, browser_cfg)
        driver_path = DriverFactory._pick_driver_path(browser_cfg, "chrome_driver_path")
        if driver_path:
            return webdriver.Chrome(service=ChromeService(driver_path), options=options)
        if ChromeDriverManager:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        DriverFactory.logger.warning("未安装 webdriver-manager，改为使用本地 ChromeDriver。")
        return webdriver.Chrome(options=options)

    @staticmethod
    def _create_chrome(headless: bool, browser_cfg: dict):
        return DriverFactory._launch_chromium(headless, browser_cfg)

    @staticmethod
    def _create_chromium(headless: bool, browser_cfg: dict):
        """通用 Chromium 内核：360 安全/极速、QQ 浏览器、奇安信等国产浏览器。

        国产浏览器普遍基于 Chromium，用 ChromeDriver + binary_location 即可驱动；
        注意其驱动主版本需与浏览器内核版本匹配，生产环境建议用 browser.driver_path
        显式指定对应版本的 chromedriver。
        """
        return DriverFactory._launch_chromium(headless, browser_cfg)

    @staticmethod
    def _apply_firefox_download_prefs(options: FirefoxOptions, headless: bool) -> None:
        """Firefox 下载偏好（与 Chromium 的 prefs 相互独立），保证导出下载静默落到指定目录。"""
        download_dir = DriverFactory._resolve_download_dir()
        if download_dir:
            options.set_preference("browser.download.dir", download_dir)
            options.set_preference("browser.download.folderList", 2)
            options.set_preference(
                "browser.helperApps.neverAsk.saveToDisk",
                "application/pdf,application/octet-stream,text/csv,text/plain,"
                "application/json,application/zip,application/vnd.ms-excel,"
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        if headless:
            options.set_preference("browser.download.manager.showWhenStarting", False)

    @staticmethod
    def _create_firefox(headless: bool, browser_cfg: dict):
        options = FirefoxOptions()
        if headless:
            options.add_argument("-headless")
        DriverFactory._apply_firefox_download_prefs(options, headless)
        driver_path = DriverFactory._pick_driver_path(browser_cfg, "firefox_driver_path")
        if driver_path:
            return webdriver.Firefox(service=FirefoxService(driver_path), options=options)
        if GeckoDriverManager:
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        return webdriver.Firefox(options=options)

    @staticmethod
    def _create_edge(headless: bool, browser_cfg: dict):
        options = DriverFactory._build_common_options(EdgeOptions(), headless)
        driver_path = DriverFactory._pick_driver_path(browser_cfg, "edge_driver_path")
        if driver_path:
            return webdriver.Edge(service=EdgeService(driver_path), options=options)
        if EdgeChromiumDriverManager:
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        return webdriver.Edge(options=options)

    @staticmethod
    def _create_safari(headless: bool, browser_cfg: dict):
        """Safari 驱动：仅 macOS 可运行（safaridriver），Windows/Linux 上明确报错。

        前置：在 macOS 上执行 `safaridriver --enable` 并允许“远程自动化”。
        Safari 无 headless 概念，headless 参数会被忽略。
        """
        if platform.system() != "Darwin":
            raise ConfigError(
                "Safari 仅支持 macOS（需先执行 safaridriver --enable 授权）",
                config_key="browser.type",
                config_file=str(Config().settings_file),
            )
        if headless:
            DriverFactory.logger.warning("Safari 不支持 headless，忽略 headless=true 设置。")
        return webdriver.Safari()

    @staticmethod
    def create_driver(browser_type: str | None = None, headless: bool | None = None):
        cfg = Config()
        browser_cfg = cfg.get("browser", {})
        browser_name = str(browser_type or browser_cfg.get("type", "chrome")).strip().lower()
        use_headless = bool(browser_cfg.get("headless", False) if headless is None else headless)

        # 别名归一：360/QQ 等国产 Chromium 浏览器统一走 chromium 分支
        if browser_name in DriverFactory.BROWSER_ALIASES:
            alias = browser_name
            browser_name = DriverFactory.BROWSER_ALIASES[alias]
            DriverFactory.logger.info("浏览器类型 %s 归一化为 %s", alias, browser_name)

        creators = {
            "chrome": DriverFactory._create_chrome,
            "chromium": DriverFactory._create_chromium,
            "firefox": DriverFactory._create_firefox,
            "edge": DriverFactory._create_edge,
            "safari": DriverFactory._create_safari,
        }
        if browser_name not in creators:
            raise ConfigError(
                "不支持的浏览器类型，可选: " + "/".join(creators)
                + "（360/QQ 等 Chromium 内核浏览器可用 chromium 并配置 browser.binary_path）",
                config_key="browser.type",
                config_file=str(cfg.settings_file),
            )

        driver = creators[browser_name](use_headless, browser_cfg)

        implicit_wait = browser_cfg.get("implicit_wait", 0)
        page_load_timeout = browser_cfg.get("page_load_timeout", 30)
        window_size = browser_cfg.get("window_size", [1920, 1080])
        maximize_window = bool(browser_cfg.get("maximize_window", True))

        if implicit_wait:
            driver.implicitly_wait(int(implicit_wait))
        if page_load_timeout:
            driver.set_page_load_timeout(int(page_load_timeout))
        if maximize_window:
            driver.maximize_window()
        elif isinstance(window_size, (list, tuple)) and len(window_size) == 2:
            driver.set_window_size(int(window_size[0]), int(window_size[1]))

        DriverFactory.logger.info("浏览器已启动: type=%s, headless=%s", browser_name, use_headless)
        return driver


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    d = DriverFactory.create_driver()
    print("current_url:", d.current_url)
    d.quit()
