# coding=utf-8
"""元素定位解析器（场景码注册版）。

沿用参考工程语义：读取 INI 配置并解析 "by>value" 定位串，与 WebDriver 解耦。
每个场景码(I01..X04) 映射到对应分组 INI 中的同名 Section。
INI 值格式：`css>.scene-card` 或 `xpath>//button[...]` 或 `=>//button[...]`(by 缺省=xpath)。
"""
from selenium.webdriver.common.by import By

from util.read_ini import ReadIni
from log.user_log import get_logger

_BY_ALIAS = {
    "xpath": By.XPATH,
    "css": By.CSS_SELECTOR,
    "id": By.ID,
    "name": By.NAME,
    "class": By.CLASS_NAME,
    "text": By.LINK_TEXT,
    "partial": By.PARTIAL_LINK_TEXT,
    "tag": By.TAG_NAME,
}

# 场景码前缀 -> 分组 INI 文件（相对工程根目录）
GROUP_INI = {
    "I": "../config/InteractElement.ini",
    "W": "../config/WaitElement.ini",
    "M": "../config/WindowElement.ini",
    "C": "../config/CompatElement.ini",
    "X": "../config/MiscElement.ini",
    "E": "../config/CryptElement.ini",
}


class FindElement:
    def __init__(self, driver=None):
        # driver 仅为兼容历史调用（self.fd = FindElement(driver)），本类与 WebDriver 解耦
        self.driver = driver
        self.logger = get_logger()

        self._ini_cache: dict[str, ReadIni] = {}
        self.locator_cache: dict[str, tuple] = {}

    def _get_ini(self, module: str) -> ReadIni:
        prefix = str(module)[0].upper()
        ini_file = GROUP_INI.get(prefix)
        if not ini_file:
            raise ValueError(f"❌ 未知的场景码前缀: {module}")
        if prefix not in self._ini_cache:
            self._ini_cache[prefix] = ReadIni(ini_file)
        return self._ini_cache[prefix]

    def _parse_locator(self, key: str, module: str) -> tuple:
        """安全解析定位信息并缓存。node/section 名 = 场景码本身。"""
        cache_key = f"{module}_{key}"
        if cache_key in self.locator_cache:
            return self.locator_cache[cache_key]

        ini_instance = self._get_ini(module)
        try:
            data = ini_instance.get_value(key=key, node=module)
        except ValueError as e:
            self.logger.error(str(e))
            raise

        parts = data.split(">", 1)
        if len(parts) == 2:
            by, value = parts[0].strip(), parts[1].strip()
            if by == "":
                by = "xpath"
        else:
            by, value = "xpath", data.strip()

        by = by.lower().replace(" ", "_")
        self.locator_cache[cache_key] = (by, value)
        return by, value

    def get_text(self, key: str, module: str) -> str:
        """获取解析后的定位器字符串（通常为 XPath），供显式等待/操作使用。"""
        by, value = self._parse_locator(key, module)
        return value if value else ""

    def get_locator(self, key: str, module: str) -> tuple:
        """获取解析后的 (By, value) 元组定位器（By 为 selenium By 枚举）。"""
        by, value = self._parse_locator(key, module)
        by_enum = _BY_ALIAS.get(by, By.XPATH)
        return by_enum, value

    def clear_cache(self):
        """清除定位器缓存。"""
        self.locator_cache.clear()
