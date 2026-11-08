# coding=utf-8
"""根级 pytest 配置：仅注册命令行级选项。

说明：pytest_addoption 必须在命令行解析前完成注册（根目录 conftest 在 parse 阶段即被加载，
而 case/ 下的子目录 conftest 解析期未必加载），故把 --browser 的注册放这里；
选项的读取与使用仍保留在 case/conftest.py 的 driver fixture 中。
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--browser",
        default=None,
        help="覆盖 settings.yaml 的 browser.type：chrome/edge/firefox/chromium/safari"
        "（360/qq 等别名自动归一为 chromium）",
    )
