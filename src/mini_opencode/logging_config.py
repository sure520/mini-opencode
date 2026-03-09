"""结构化日志配置"""
import logging
import structlog


# 配置 structlog
structlog.configure(
    processors=[
        # 添加时间戳
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        # 添加进程和线程信息
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # 格式化输出
        structlog.dev.ConsoleRenderer(
            colors=True,  # 启用彩色输出
        ),
    ],
    # 使用标准库的 logger
    logger_factory=structlog.stdlib.LoggerFactory(),
    # 使用标准库的处理器
    wrapper_class=structlog.stdlib.BoundLogger,
    # 缓存标准库的 logger
    cache_logger_on_first_use=True,
)


def get_logger(name: str):
    """获取结构化日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        结构化日志记录器
    """
    return structlog.get_logger(name)


# 配置标准库日志
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 移除默认处理器
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# 添加控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 使用 structlog 的 ProcessorFormatter
formatter = structlog.stdlib.ProcessorFormatter(
    processor=structlog.dev.ConsoleRenderer(),
)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)
