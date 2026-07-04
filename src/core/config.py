"""
Newssys 2.0 配置管理
使用 pydantic-settings 解析环境变量
"""

import logging
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 加载 .env 文件
ENV_FILE = Path(__file__).parent.parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
    logger = logging.getLogger(__name__)
    logger.info(f"Loaded .env from: {ENV_FILE}")
else:
    logger = logging.getLogger(__name__)
    logger.warning(f".env file not found at: {ENV_FILE}")


class DatabaseSettings(BaseSettings):
    """数据库配置 - 支持 MySQL 和 SQLite"""

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 数据库类型: mysql 或 sqlite
    type: str = "sqlite"

    # MySQL 配置
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    charset: str = "utf8mb4"

    # 通用配置
    name: str = "newssys"  # MySQL: 数据库名, SQLite: 文件名
    pool_size: int = 10
    max_overflow: int = 20
    sqlite_timeout: float = 30.0
    sqlite_busy_timeout_ms: int = 30000
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    @property
    def is_mysql(self) -> bool:
        """是否为 MySQL 数据库"""
        return self.type == "mysql"

    @property
    def is_sqlite(self) -> bool:
        """是否为 SQLite 数据库"""
        return self.type == "sqlite"

    @property
    def url(self) -> str:
        """生成数据库连接 URL，支持 MySQL 和 SQLite"""
        if self.database_url:
            return self.database_url
        if self.type == "sqlite":
            # SQLite 使用文件路径
            db_path = Path(__file__).parent.parent.parent / f"{self.name}.db"
            return f"sqlite+aiosqlite:///{db_path}"
        else:
            # MySQL 使用网络连接
            return f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}?charset={self.charset}"


class AISettings(BaseSettings):
    """AI 引擎配置"""

    model_config = SettingsConfigDict(
        env_prefix="AI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: str = Field(
        default="https://api.siliconflow.cn/v1",
        validation_alias=AliasChoices("AI_BASE_URL", "OPENAI_BASE_URL", "base_url"),
    )
    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AI_API_KEY", "OPENAI_API_KEY", "api_key"),
    )
    model: str = Field(
        default="deepseek-ai/DeepSeek-V3",
        validation_alias=AliasChoices("AI_MODEL", "OPENAI_MODEL", "model"),
    )
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout: int = 60


class CrawlerSettings(BaseSettings):
    """爬虫配置"""

    max_concurrent: int = 10
    default_timeout: int = 30
    user_agent: str = "Newssys Intelligence Bot/2.0"
    respect_robots: bool = True
    default_delay: float = 1.0

    class Config:
        env_prefix = "CRAWLER_"


class APISettings(BaseSettings):
    """API 服务配置"""

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 4
    log_level: str = "info"

    class Config:
        env_prefix = "API_"


class SearchEngineSettings(BaseSettings):
    """搜索引擎配置"""

    timeout: int = 10
    max_results: int = 50
    default_region: str = "kz-kk"

    class Config:
        env_prefix = "SEARCH_ENGINE_"


class ReportSettings(BaseSettings):
    """报告生成配置"""

    max_articles: int = 100
    default_time_range: str = "week"
    enable_cache: bool = True

    class Config:
        env_prefix = "REPORT_"


class LogSettings(BaseSettings):
    """日志配置"""

    level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "LOG_LEVEL".lower(), "level"),
    )
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/newssys.log"
    rotation: str = "midnight"
    retention: int = 30

    class Config:
        env_prefix = "LOG_"


class RuntimeSettings(BaseSettings):
    """运行时配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enable_scheduler: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_SCHEDULER", "enable_scheduler"),
    )
    heartbeat_type: str = Field(
        default="auto",
        validation_alias=AliasChoices("HEARTBEAT_TYPE", "heartbeat_type"),
        description="心跳类型: auto (按DB类型选择), file (文件), database (数据库)",
    )
    worker_id: str = Field(
        default="",
        validation_alias=AliasChoices("WORKER_ID", "worker_id"),
        description="Worker 实例唯一标识，为空时自动生成",
    )
    scheduler_heartbeat_file: str = Field(
        default="/tmp/newssys-scheduler-heartbeat",
        validation_alias=AliasChoices("SCHEDULER_HEARTBEAT_FILE", "scheduler_heartbeat_file"),
    )
    scheduler_heartbeat_interval_seconds: int = Field(
        default=15,
        validation_alias=AliasChoices(
            "SCHEDULER_HEARTBEAT_INTERVAL_SECONDS",
            "scheduler_heartbeat_interval_seconds",
        ),
    )
    scheduler_heartbeat_stale_seconds: int = Field(
        default=90,
        validation_alias=AliasChoices(
            "SCHEDULER_HEARTBEAT_STALE_SECONDS",
            "scheduler_heartbeat_stale_seconds",
        ),
    )
    report_heartbeat_file: str = Field(
        default="/tmp/newssys-report-heartbeat",
        validation_alias=AliasChoices("REPORT_HEARTBEAT_FILE", "report_heartbeat_file"),
    )
    report_heartbeat_stale_seconds: int = Field(
        default=90,
        validation_alias=AliasChoices(
            "REPORT_HEARTBEAT_STALE_SECONDS",
            "report_heartbeat_stale_seconds",
        ),
    )
    crawl_heartbeat_file: str = Field(
        default="/tmp/newssys-crawl-heartbeat",
        validation_alias=AliasChoices("CRAWL_HEARTBEAT_FILE", "crawl_heartbeat_file"),
    )
    crawl_heartbeat_stale_seconds: int = Field(
        default=90,
        validation_alias=AliasChoices(
            "CRAWL_HEARTBEAT_STALE_SECONDS",
            "crawl_heartbeat_stale_seconds",
        ),
    )
    search_heartbeat_file: str = Field(
        default="/tmp/newssys-search-heartbeat",
        validation_alias=AliasChoices("SEARCH_HEARTBEAT_FILE", "search_heartbeat_file"),
    )
    search_heartbeat_stale_seconds: int = Field(
        default=90,
        validation_alias=AliasChoices(
            "SEARCH_HEARTBEAT_STALE_SECONDS",
            "search_heartbeat_stale_seconds",
        ),
    )
    ai_heartbeat_file: str = Field(
        default="/tmp/newssys-ai-heartbeat",
        validation_alias=AliasChoices("AI_HEARTBEAT_FILE", "ai_heartbeat_file"),
    )
    ai_heartbeat_stale_seconds: int = Field(
        default=90,
        validation_alias=AliasChoices(
            "AI_HEARTBEAT_STALE_SECONDS",
            "ai_heartbeat_stale_seconds",
        ),
    )
    sitemap_heartbeat_file: str = Field(
        default="/tmp/newssys-sitemap-heartbeat",
        validation_alias=AliasChoices("SITEMAP_HEARTBEAT_FILE", "sitemap_heartbeat_file"),
    )
    sitemap_heartbeat_stale_seconds: int = Field(
        default=90,
        validation_alias=AliasChoices(
            "SITEMAP_HEARTBEAT_STALE_SECONDS",
            "sitemap_heartbeat_stale_seconds",
        ),
    )
    access_gate_secret: str = Field(
        default="newssys-gate-secret",
        validation_alias=AliasChoices("ACCESS_GATE_SECRET", "access_gate_secret"),
        description="访问密码生成密钥，修改后每日密码不同",
    )


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ai: AISettings = Field(default_factory=AISettings)
    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    api: APISettings = Field(default_factory=APISettings)
    search_engine: SearchEngineSettings = Field(default_factory=SearchEngineSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    debug: bool = False
    DEBUG: bool = False  # 别名，兼容旧代码

    @property
    def CORS_ORIGINS(self) -> List[str]:
        """兼容旧代码中的大写属性访问。"""
        return self.cors_origins

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # 尝试解析 JSON 格式
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # 简单的逗号分隔
                return [origin.strip() for origin in v.split(",")]
        return v


# 全局配置实例
settings = Settings()


def init_logging():
    """初始化日志系统"""
    import logging.handlers
    import os
    import warnings

    log_settings = settings.log

    # 创建日志目录
    log_dir = os.path.dirname(log_settings.file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 过滤第三方库的 DeprecationWarning
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="aiosqlite")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="bs4")

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_settings.level.upper()))

    # 清除现有处理器
    root_logger.handlers.clear()

    # 格式化器
    formatter = logging.Formatter(log_settings.format)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（按天轮转）
    if log_settings.file_path:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_settings.file_path,
            when=log_settings.rotation,
            interval=1,
            backupCount=log_settings.retention,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.suffix = "%Y-%m-%d"
        root_logger.addHandler(file_handler)

    logger.info(f"Logging initialized: {log_settings.level}")


# 导出配置
__all__ = ["settings", "init_logging"]
