"""本地翻译服务日志配置。

双输出：stderr 控制台 + logs/ 目录按天轮转文件。
日志级别通过 LOG_LEVEL 环境变量控制（默认 INFO）。
"""

import logging
import os
import shutil
from logging.handlers import TimedRotatingFileHandler

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "local-translator.log")

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 统一格式：[时间] [级别] 模块:函数 消息
FORMAT = "[%(asctime)s] %(levelname)s %(name)s:%(funcName)s %(message)s"

logger = logging.getLogger("local-translator")
logger.setLevel(LOG_LEVEL)

# 控制台 handler（stderr）
console_handler = logging.StreamHandler()
console_handler.setLevel(LOG_LEVEL)
console_handler.setFormatter(logging.Formatter(FORMAT))
logger.addHandler(console_handler)

# 文件 handler（按天轮转）
file_handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="midnight",
    interval=1,
    backupCount=0,  # 保留所有历史，不自动删除
    encoding="utf-8",
)
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(logging.Formatter(FORMAT))
file_handler.namer = lambda name: name  # Default format is already local-translator.log.YYYY-MM-DD
file_handler.rotator = lambda src, dst: shutil.move(src, dst)
logger.addHandler(file_handler)
