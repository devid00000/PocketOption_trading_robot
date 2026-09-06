"""
Модуль конфигурации приложения.
Использует pydantic-settings для управления настройками.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Настройки авторизации."""
    
    email: str = Field(default="", description="Email для авторизации")
    password: str = Field(default="", description="Пароль для авторизации")
    session_cookie: Optional[str] = Field(default=None, description="Session cookie (альтернатива паролю)")
    is_demo: bool = Field(default=True, description="Использовать демо-счёт")
    
    model_config = SettingsConfigDict(env_prefix="PO_AUTH_", env_file=".env")


class ConnectionSettings(BaseSettings):
    """Настройки подключения."""
    
    platform_url: str = Field(default="https://pocketoption.com", description="URL платформы")
    ws_server: str = Field(default="wss://po.market", description="WebSocket сервер")
    api_server: str = Field(default="https://pocketoption.expert/api", description="API сервер")
    timeout: int = Field(default=30, description="Таймаут подключения в секундах")
    reconnect_delay: int = Field(default=5, description="Задержка перед переподключением")
    max_reconnect_attempts: int = Field(default=10, description="Максимум попыток переподключения")
    
    model_config = SettingsConfigDict(env_prefix="PO_CONN_", env_file=".env")


class TradingSettings(BaseSettings):
    """Торговые настройки по умолчанию."""
    
    default_amount: float = Field(default=1.0, description="Сумма сделки по умолчанию")
    default_duration: int = Field(default=60, description="Длительность сделки в секундах")
    max_daily_loss: float = Field(default=100.0, description="Максимальный дневной убыток")
    max_daily_profit: float = Field(default=500.0, description="Максимальная дневная прибыль")
    stop_on_loss: bool = Field(default=True, description="Остановить торговлю при достижении лимита убытка")
    
    model_config = SettingsConfigDict(env_prefix="PO_TRADE_", env_file=".env")


class AppSettings(BaseSettings):
    """Основные настройки приложения."""
    
    app_name: str = "Pocket Option Robot"
    version: str = "0.1.0"
    debug: bool = Field(default=False, description="Режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    
    # Вложенные настройки
    auth: AuthSettings = Field(default_factory=AuthSettings)
    connection: ConnectionSettings = Field(default_factory=ConnectionSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    
    model_config = SettingsConfigDict(env_file=".env")


# Глобальный экземпляр настроек
settings = AppSettings()


def get_settings() -> AppSettings:
    """Получить настройки приложения."""
    return settings


def update_auth_settings(email: Optional[str] = None, 
                         password: Optional[str] = None,
                         is_demo: Optional[bool] = None) -> None:
    """
    Обновить настройки авторизации.
    
    Args:
        email: Email для авторизации
        password: Пароль для авторизации
        is_demo: Использовать демо-счёт
    """
    if email is not None:
        settings.auth.email = email
    if password is not None:
        settings.auth.password = password
    if is_demo is not None:
        settings.auth.is_demo = is_demo


__all__ = ["settings", "get_settings", "update_auth_settings", 
           "AppSettings", "AuthSettings", "ConnectionSettings", "TradingSettings"]
