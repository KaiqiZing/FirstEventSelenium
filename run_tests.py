"""多模式测试运行脚本。"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "report"
ALLURE_RESULTS_DIR = REPORT_DIR / "allure-results"
ALLURE_HTML_DIR = REPORT_DIR / "allure-html"


def run_command(command: list[str]) -> int:
    print("执行命令:", " ".join(command))
    completed = subprocess.run(command, cwd=BASE_DIR)
    return completed.returncode


def build_pytest_command(mode: str, extra_args: list[str]) -> list[str]:
    command = [sys.executable, "-m", "pytest"]
    if mode == "smoke":
        command.extend(["-m", "smoke"])
    elif mode == "regression":
        command.extend(["-m", "regression"])
    elif mode == "allure":
        ALLURE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        command.extend(["--alluredir", str(ALLURE_RESULTS_DIR)])
    command.extend(extra_args)
    return command


def generate_allure_report() -> int:
    allure_bin = shutil.which("allure")
    if not allure_bin:
        print("未检测到 allure 命令，已保留结果目录:", ALLURE_RESULTS_DIR)
        return 0

    ALLURE_HTML_DIR.mkdir(parents=True, exist_ok=True)
    return run_command(
        [
            allure_bin,
            "generate",
            str(ALLURE_RESULTS_DIR),
            "-o",
            str(ALLURE_HTML_DIR),
            "--clean",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FirstEventSelenium 全场景自动化运行脚本")
    parser.add_argument(
        "--mode",
        choices=["smoke", "regression", "all", "allure"],
        default="all",
        help="运行模式",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="透传给 pytest 的额外参数，例如 -- -k I01",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pytest_args = args.pytest_args
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]

    exit_code = run_command(build_pytest_command(args.mode, pytest_args))
    if exit_code != 0:
        return exit_code

    if args.mode == "allure":
        return generate_allure_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
