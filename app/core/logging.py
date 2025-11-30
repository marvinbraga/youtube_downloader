# app/core/logging.py
import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Handler que intercepta logs do logging padrão e redireciona para o loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Obtém o nível correspondente do loguru
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Encontra o caller que originou o log
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(level: str = "INFO") -> None:
    """
    Configura o loguru como handler principal para todos os logs.

    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Remove handlers padrão do loguru
    logger.remove()

    # Adiciona handler para stdout com formato customizado
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
    )

    # Loggers que queremos interceptar
    loggers_to_intercept = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy",
        "sqlalchemy.engine",
        "aiosqlite",
        "httpx",
        "httpcore",
    ]

    # Configura o logging padrão para usar nosso interceptor
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Intercepta cada logger específico
    for logger_name in loggers_to_intercept:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    logger.info("Sistema de logging configurado com loguru")
