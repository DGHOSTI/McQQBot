# -*- coding: utf-8 -*-
"""统一日志管理：所有日志（应用 + botpy 内部）集中输出到 logs/ 目录。

调用 ``setup_logging()`` 后，项目内任何 ``logging.getLogger(__name__)``
都会写入统一文件与控制台；botpy 库内部日志同样经由 root 落入统一文件，
不再像默认那样散落在当前目录生成 botpy.log / DEBUG.log。
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOG_DIR = os.path.join(BASE_DIR, "logs")
DEFAULT_LOG_FILE = "bot.log"

# 文件日志：带时间、模块、行号，便于回溯
_FILE_FORMAT = "%(asctime)s\t[%(levelname)s]\t(%(name)s:%(lineno)s)%(funcName)s\t%(message)s"
# 控制台：简洁可读
_CONSOLE_FORMAT = "[%(levelname)s] %(message)s"

__all__ = ["setup_logging", "DEFAULT_LOG_DIR"]


def setup_logging(
    log_dir: str = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
    level: int = logging.INFO,
    backup_count: int = 14,
) -> logging.Logger:
    """配置统一日志并返回应用根 logger（logger 名 "mcbot"）。"""
    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    # botpy 在 import 时 basicConfig 会给 root 添加 StreamHandler，这里接管后重建
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # 文件：按天轮转
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, log_file),
        when="midnight",
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    root.addHandler(file_handler)

    # 控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    root.addHandler(console_handler)

    root.setLevel(level)

    # botpy logger：交给 root 统一管理，避免其自行落盘
    botpy_logger = logging.getLogger("botpy")
    botpy_logger.handlers = []
    botpy_logger.propagate = True
    botpy_logger.setLevel(level)

    return logging.getLogger("mcbot")