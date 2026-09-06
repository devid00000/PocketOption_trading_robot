"""
Модуль логирования для Pocket Option Robot.
Использует loguru для удобного и красивого логирования.
"""

import sys
from pathlib import Path
from loguru import logger
from config.paths import LOGS_DIR


def setup_logger(log_file: str = "pocket_option_robot.log", level: str = "INFO") -> None:
    """
    Настройка логгера.

    Args:
        log_file: Имя файла для логов
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Очищаем все существующие обработчики
    logger.remove()

    # Добавляем консольный обработчик с цветным выводом
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=level,
        colorize=True,
    )

    # Добавляем файловый обработчик
    log_path = LOGS_DIR / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )

    logger.info("Логгер инициализирован")


# Создаём удобный интерфейс для логирования
class Logger:
    """Класс для логирования с поддержкой контекста."""
    
    def __init__(self, context: str = ""):
        """
        Инициализация логгера.
        
        Args:
            context: Контекст для логирования (например, имя модуля или компонента)
        """
        self.context = context
    
    def _format_message(self, message: str) -> str:
        """Форматирование сообщения с контекстом."""
        if self.context:
            return f"[{self.context}] {message}"
        return message
    
    def debug(self, message: str) -> None:
        logger.debug(self._format_message(message))
    
    def info(self, message: str) -> None:
        logger.info(self._format_message(message))
    
    def warning(self, message: str) -> None:
        logger.warning(self._format_message(message))
    
    def error(self, message: str) -> None:
        logger.error(self._format_message(message))
    
    def critical(self, message: str) -> None:
        logger.critical(self._format_message(message))
    
    def success(self, message: str) -> None:
        logger.success(self._format_message(message))


# Экспортируем основной интерфейс
__all__ = ["setup_logger", "Logger"]
