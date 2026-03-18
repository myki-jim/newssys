"""
worker 专用日志系统
提供中文板块名、彩色控制台输出和按板块分文件轮转。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from src.core.config import settings

MAX_LOG_LINES_PER_FILE = 30000
DEFAULT_WORKER_LOG_DIR = "logs/worker"


@dataclass(frozen=True)
class WorkerLogSection:
    key: str
    label: str
    color: str
    prefix: str
    logger_prefixes: tuple[str, ...]


SECTIONS: tuple[WorkerLogSection, ...] = (
    WorkerLogSection(
        key="crawl",
        label="文章爬取",
        color="\033[38;5;208m",
        prefix="crawl",
        logger_prefixes=(
            "src.services.collector",
            "src.services.universal_scraper",
            "src.services.sitemap_parser",
            "src.services.sitemap_service",
            "src.services.smart_extractor",
            "src.services.robots_handler",
            "src.services.site_discovery",
        ),
    ),
    WorkerLogSection(
        key="report",
        label="报告生成",
        color="\033[34m",
        prefix="report",
        logger_prefixes=(
            "src.services.report_agent",
            "src.services.keyword_generator",
            "src.services.article_clustering",
            "src.services.event_extraction",
            "src.services.aggregator",
            "src.services.openai_client",
        ),
    ),
    WorkerLogSection(
        key="scheduler",
        label="调度中心",
        color="\033[38;5;135m",
        prefix="scheduler",
        logger_prefixes=(
            "src.services.scheduler_service",
            "src.services.schedule_executor",
        ),
    ),
    WorkerLogSection(
        key="task",
        label="任务队列",
        color="\033[38;5;51m",
        prefix="task",
        logger_prefixes=(
            "src.services.task_worker_service",
            "src.services.task_manager",
            "src.services.task_executors",
        ),
    ),
    WorkerLogSection(
        key="search",
        label="搜索导入",
        color="\033[93m",
        prefix="search",
        logger_prefixes=(
            "src.services.search_engine",
        ),
    ),
    WorkerLogSection(
        key="ai",
        label="AI 对话",
        color="\033[38;5;39m",
        prefix="ai",
        logger_prefixes=(
            "src.services.ai_agent",
        ),
    ),
    WorkerLogSection(
        key="system",
        label="系统运行",
        color="\033[38;5;118m",
        prefix="system",
        logger_prefixes=(
            "src.worker",
            "src.worker.main",
            "asyncio",
            "src.core.database",
            "src.core.config",
            "src.worker.runtime",
        ),
    ),
)

DEFAULT_SECTION = next(section for section in SECTIONS if section.key == "system")
RESET = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"


def resolve_section(logger_name: str) -> WorkerLogSection:
    if logger_name == "src.services.schedule_executor":
        return DEFAULT_SECTION
    for section in SECTIONS:
        if any(logger_name.startswith(prefix) for prefix in section.logger_prefixes):
            return section
    return DEFAULT_SECTION


class WorkerSectionFilter(logging.Filter):
    """给日志记录补充 worker 板块信息。"""

    def filter(self, record: logging.LogRecord) -> bool:
        section = resolve_section(record.name)
        message = record.getMessage()

        if record.name == "src.services.schedule_executor":
            if any(token in message for token in ("搜索关键词", "搜索完成", "所有关键词搜索完成")):
                section = next(item for item in SECTIONS if item.key == "search")
            elif any(token in message for token in ("Sitemap", "爬取", "内容太短", "成功爬取文章", "源 ")):
                section = next(item for item in SECTIONS if item.key == "crawl")
            else:
                section = next(item for item in SECTIONS if item.key == "scheduler")

        record.worker_section_key = section.key
        record.worker_section_label = section.label
        record.worker_section_color = section.color
        return True


class SectionOnlyFilter(logging.Filter):
    """只保留指定板块的日志。"""

    def __init__(self, section_key: str):
        super().__init__()
        self.section_key = section_key

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "worker_section_key", None) == self.section_key


class ErrorOnlyFilter(logging.Filter):
    """仅保留错误日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


class WorkerConsoleFormatter(logging.Formatter):
    """控制台彩色输出。"""

    def format(self, record: logging.LogRecord) -> str:
        time_text = self.formatTime(record, "%H:%M:%S")
        label = getattr(record, "worker_section_label", "系统运行")
        section_color = getattr(record, "worker_section_color", "")

        if record.levelno >= logging.ERROR:
            level_color = RED
            level_text = "错误"
        elif record.levelno >= logging.WARNING:
            level_color = YELLOW
            level_text = "警告"
        else:
            level_color = section_color
            level_text = None

        message = record.getMessage()
        parts = [f"{time_text} {section_color}[{label}]{RESET}"]
        if level_text:
            parts.append(f"{level_color}{level_text}{RESET}")
        text_color = level_color if record.levelno >= logging.WARNING else section_color
        parts.append(f"{text_color}{message}{RESET}")
        rendered = " ".join(parts)

        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            exception_color = level_color if record.levelno >= logging.WARNING else section_color
            rendered = f"{rendered}\n{exception_color}{exception_text}{RESET}"
        return rendered


class WorkerConsoleHandler(logging.StreamHandler):
    """在板块切换时输出分隔条。"""

    def __init__(self) -> None:
        super().__init__()
        self._last_section_key: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            section_key = getattr(record, "worker_section_key", "system")
            section_label = getattr(record, "worker_section_label", "系统运行")
            section_color = getattr(record, "worker_section_color", "")
            if section_key != self._last_section_key:
                self.stream.write(f"\n{section_color}========== {section_label} =========={RESET}\n")
                self._last_section_key = section_key
            super().emit(record)
        except Exception:
            self.handleError(record)


class WorkerFileFormatter(logging.Formatter):
    """极简文件日志格式。"""

    def format(self, record: logging.LogRecord) -> str:
        time_text = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        label = getattr(record, "worker_section_label", "系统运行")
        level = record.levelname
        message = record.getMessage()
        rendered = f"{time_text} [{label}] {level} {message}"
        if record.exc_info:
            rendered = f"{rendered}\n{self.formatException(record.exc_info)}"
        return rendered


class LineRotatingFileHandler(logging.Handler):
    """按行数轮转的文件处理器。"""

    def __init__(self, directory: Path, prefix: str, max_lines: int = MAX_LOG_LINES_PER_FILE):
        super().__init__()
        self.directory = directory
        self.prefix = prefix
        self.max_lines = max_lines
        self.directory.mkdir(parents=True, exist_ok=True)
        self.stream = None
        self.current_index = 1
        self.current_line_count = 0
        self._open_latest_file()

    def _existing_indices(self) -> list[int]:
        indices: list[int] = []
        for path in self.directory.glob(f"{self.prefix}-*.log"):
            try:
                indices.append(int(path.stem.split("-")[-1]))
            except ValueError:
                continue
        return sorted(indices)

    def _path_for_index(self, index: int) -> Path:
        return self.directory / f"{self.prefix}-{index:04d}.log"

    def _count_lines(self, path: Path) -> int:
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)

    def _open_latest_file(self) -> None:
        indices = self._existing_indices()
        if not indices:
            self.current_index = 1
            self.current_line_count = 0
            self.stream = self._path_for_index(self.current_index).open("a", encoding="utf-8")
            return

        latest_index = indices[-1]
        latest_path = self._path_for_index(latest_index)
        latest_lines = self._count_lines(latest_path)
        if latest_lines >= self.max_lines:
            self.current_index = latest_index + 1
            self.current_line_count = 0
        else:
            self.current_index = latest_index
            self.current_line_count = latest_lines

        self.stream = self._path_for_index(self.current_index).open("a", encoding="utf-8")

    def _rotate_if_needed(self, lines_to_write: int) -> None:
        if self.current_line_count + lines_to_write <= self.max_lines:
            return
        if self.stream:
            self.stream.close()
        self.current_index += 1
        self.current_line_count = 0
        self.stream = self._path_for_index(self.current_index).open("a", encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            line_count = max(len(msg.splitlines()), 1)
            self._rotate_if_needed(line_count)
            if self.stream is None:
                self._open_latest_file()
            self.stream.write(msg + "\n")
            self.stream.flush()
            self.current_line_count += line_count
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        try:
            if self.stream:
                self.stream.close()
        finally:
            self.stream = None
            super().close()


def _build_worker_log_dir() -> Path:
    configured_dir = os.getenv("WORKER_LOG_DIR")
    if configured_dir:
        return Path(configured_dir)
    return Path(settings.log.file_path).parent / "worker"


def init_worker_logging() -> None:
    """初始化 worker 专用日志输出。"""
    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning, module="aiosqlite")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="bs4")
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log.level.upper()))
    root_logger.handlers.clear()

    section_filter = WorkerSectionFilter()
    worker_log_dir = _build_worker_log_dir()

    console_handler = WorkerConsoleHandler()
    console_handler.setFormatter(WorkerConsoleFormatter())
    console_handler.addFilter(section_filter)
    root_logger.addHandler(console_handler)

    file_formatter = WorkerFileFormatter()
    for section in SECTIONS:
        handler = LineRotatingFileHandler(worker_log_dir, section.prefix)
        handler.setFormatter(file_formatter)
        handler.addFilter(section_filter)
        handler.addFilter(SectionOnlyFilter(section.key))
        root_logger.addHandler(handler)

    error_handler = LineRotatingFileHandler(worker_log_dir, "error")
    error_handler.setFormatter(file_formatter)
    error_handler.addFilter(section_filter)
    error_handler.addFilter(ErrorOnlyFilter())
    root_logger.addHandler(error_handler)

    for noisy_logger in (
        "httpx",
        "httpcore",
        "aiosqlite",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "uvicorn.access",
        "uvicorn.error",
        "jieba",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logging.getLogger("src.worker.main").info(
        "worker 日志系统已切换为分板块模式，目录: %s",
        worker_log_dir,
    )
