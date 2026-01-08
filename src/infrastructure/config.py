"""
配置管理模块
使用 pydantic-settings 管理应用配置
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=3306, description="数据库端口")
    username: str = Field(default="root", description="数据库用户名")
    password: str = Field(default="", description="数据库密码")
    database: str = Field(default="newssys", description="数据库名称")
    charset: str = Field(default="utf8mb4", description="字符集")
    pool_size: int = Field(default=10, description="连接池大小")
    max_overflow: int = Field(default=20, description="连接池最大溢出连接数")
    pool_recycle: int = Field(default=3600, description="连接回收时间（秒）")
    echo: bool = Field(default=False, description="是否打印 SQL 语句")

    @property
    def url(self) -> str:
        """生成数据库连接 URL"""
        return f"mysql+aiomysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"

    model_config = SettingsConfigDict(env_prefix="DB_")


class LogConfig(BaseSettings):
    """日志配置"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="日志级别"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式",
    )
    file_path: str | None = Field(default=None, description="日志文件路径")
    max_bytes: int = Field(default=10485760, description="日志文件最大大小（10MB）")
    backup_count: int = Field(default=5, description="日志文件备份数量")

    model_config = SettingsConfigDict(env_prefix="LOG_")


class CrawlerConfig(BaseSettings):
    """爬虫配置"""

    concurrent_limit: int = Field(default=5, description="并发爬取限制")
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    retry_times: int = Field(default=3, description="重试次数")
    retry_delay: int = Field(default=1, description="重试延迟（秒）")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        description="User-Agent",
    )

    model_config = SettingsConfigDict(env_prefix="CRAWLER_")


class AppConfig(BaseSettings):
    """应用配置"""

    app_name: str = Field(default="Newssys", description="应用名称")
    debug: bool = Field(default=False, description="调试模式")
    environment: Literal["development", "testing", "production"] = Field(
        default="development", description="运行环境"
    )

    model_config = SettingsConfigDict(env_prefix="APP_")


class Settings(BaseSettings):
    """全局配置类"""

    app: AppConfig = Field(default_factory=AppConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    获取配置单例
    使用 lru_cache 确保配置只加载一次
    """
    return Settings()
