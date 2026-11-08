# coding=utf-8
from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler


def get_logger(logger_name="UIEventTest"):
    """
    获取配置好的全局 Logger 对象（控制台 + 按天滚动文件）。
    """
    logger = logging.getLogger(logger_name)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, f"{logger_name}.log")

        file_handle = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handle.suffix = "%Y-%m-%d.log"
        file_handle.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(filename)s--> %(funcName)s %(levelno)s: %(levelname)s ----->%(message)s'
        )
        file_handle.setFormatter(formatter)

        console_handle = logging.StreamHandler()
        console_handle.setLevel(logging.INFO)
        console_handle.setFormatter(formatter)

        logger.addHandler(file_handle)
        logger.addHandler(console_handle)

    return logger
