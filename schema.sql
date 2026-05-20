-- Newssys 2.0 完整数据库建表语句
-- MySQL 8.0 兼容

CREATE DATABASE IF NOT EXISTS `newssys` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `newssys`;

-- ============================================
-- 爬虫源配置表
-- ============================================
CREATE TABLE IF NOT EXISTS `crawl_sources` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '爬虫源 ID',
    `site_name` VARCHAR(255) NOT NULL COMMENT '站点名称',
    `base_url` VARCHAR(1024) NOT NULL COMMENT '基础 URL',
    `parser_config` JSON NOT NULL COMMENT '解析器配置（选择器等）',
    `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
    `crawl_interval` INT UNSIGNED NOT NULL DEFAULT 3600 COMMENT '爬取间隔（秒）',
    `robots_status` ENUM('pending','compliant','restricted','not_found','error') NOT NULL DEFAULT 'pending' COMMENT 'Robots.txt 状态',
    `crawl_delay` INT UNSIGNED DEFAULT NULL COMMENT 'Robots.txt 指定的抓取延迟',
    `robots_fetched_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Robots.txt 最后获取时间',
    `sitemap_url` VARCHAR(2048) DEFAULT NULL COMMENT '主 Sitemap URL',
    `sitemap_last_fetched` TIMESTAMP NULL DEFAULT NULL COMMENT 'Sitemap 最后获取时间',
    `sitemap_entry_count` INT UNSIGNED DEFAULT NULL COMMENT 'Sitemap 条目数量',
    `last_crawled_at` TIMESTAMP NULL DEFAULT NULL COMMENT '最后爬取时间',
    `success_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '成功爬取次数',
    `failure_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '失败爬取次数',
    `last_error` TEXT DEFAULT NULL COMMENT '最后错误信息',
    `discovery_method` ENUM('sitemap','list','hybrid') NOT NULL DEFAULT 'sitemap' COMMENT 'URL 发现策略',
    `extra_data` JSON DEFAULT NULL COMMENT '额外元数据',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_site_name` (`site_name`),
    INDEX `idx_enabled` (`enabled`),
    INDEX `idx_discovery_method` (`discovery_method`),
    INDEX `idx_robots_status` (`robots_status`),
    INDEX `idx_enabled_last_crawled` (`enabled`, `last_crawled_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爬虫源配置表';

-- ============================================
-- 文章表
-- ============================================
CREATE TABLE IF NOT EXISTS `articles` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '文章 ID',
    `url_hash` CHAR(32) NOT NULL COMMENT 'URL 的 MD5 哈希值',
    `url` VARCHAR(2048) NOT NULL COMMENT '文章 URL',
    `title` VARCHAR(512) NOT NULL COMMENT '文章标题',
    `content` TEXT COMMENT '文章内容',
    `content_hash` CHAR(64) DEFAULT NULL COMMENT '内容 SHA256 哈希值',
    `publish_time` TIMESTAMP NULL DEFAULT NULL COMMENT '发布时间',
    `author` VARCHAR(255) DEFAULT NULL COMMENT '作者',
    `source_id` INT UNSIGNED NOT NULL COMMENT '爬虫源 ID',
    `status` ENUM('raw','processed','synced','failed','low_quality') NOT NULL DEFAULT 'raw' COMMENT '文章语义状态',
    `fetch_status` ENUM('pending','success','retry','failed') NOT NULL DEFAULT 'pending' COMMENT '抓取任务状态',
    `error_message` TEXT COMMENT '错误信息',
    `error_msg` TEXT COMMENT '错误信息（新字段）',
    `crawled_at` TIMESTAMP NULL DEFAULT NULL COMMENT '爬取时间',
    `processed_at` TIMESTAMP NULL DEFAULT NULL COMMENT '处理时间',
    `synced_at` TIMESTAMP NULL DEFAULT NULL COMMENT '同步时间',
    `retry_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '重试次数',
    `last_retry_at` TIMESTAMP NULL DEFAULT NULL COMMENT '最后重试时间',
    `extra_data` JSON DEFAULT NULL COMMENT '额外元数据',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_url_hash` (`url_hash`),
    INDEX `idx_source_id` (`source_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_fetch_status` (`fetch_status`),
    INDEX `idx_publish_time` (`publish_time`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_source_status_time` (`source_id`, `status`, `publish_time`),
    INDEX `idx_fetch_status_retry` (`fetch_status`, `retry_count`),
    INDEX `idx_content_hash` (`content_hash`),
    INDEX `idx_status_publish_time` (`status`, `publish_time`),
    CONSTRAINT `fk_articles_source` FOREIGN KEY (`source_id`) REFERENCES `crawl_sources` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章表';

-- ============================================
-- Sitemap 表
-- ============================================
CREATE TABLE IF NOT EXISTS `sitemaps` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `source_id` INT UNSIGNED NOT NULL,
    `url` VARCHAR(768) NOT NULL COMMENT 'Sitemap URL',
    `last_fetched` TIMESTAMP NULL DEFAULT NULL,
    `fetch_status` ENUM('pending','success','failed') NOT NULL DEFAULT 'pending',
    `article_count` INT UNSIGNED DEFAULT 0,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_sitemap_url` (`url`),
    INDEX `idx_source_id` (`source_id`),
    CONSTRAINT `fk_sitemaps_source` FOREIGN KEY (`source_id`) REFERENCES `crawl_sources` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Sitemap 表';

-- ============================================
-- 待爬文章表
-- ============================================
CREATE TABLE IF NOT EXISTS `pending_articles` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `source_id` INT UNSIGNED NOT NULL,
    `sitemap_id` INT UNSIGNED DEFAULT NULL,
    `url` VARCHAR(2048) NOT NULL,
    `url_hash` CHAR(32) NOT NULL,
    `title` VARCHAR(512) DEFAULT NULL,
    `publish_time` TIMESTAMP NULL DEFAULT NULL,
    `status` ENUM('pending','crawling','completed','failed','abandoned','low_quality') NOT NULL DEFAULT 'pending',
    `error_message` TEXT DEFAULT NULL,
    `retry_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `last_retry_at` TIMESTAMP NULL DEFAULT NULL,
    `extra_data` JSON DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_url_hash` (`url_hash`),
    INDEX `idx_source_id` (`source_id`),
    INDEX `idx_sitemap_id` (`sitemap_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_publish_time` (`publish_time`),
    CONSTRAINT `fk_pending_source` FOREIGN KEY (`source_id`) REFERENCES `crawl_sources` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='待爬文章表';

-- ============================================
-- 任务表
-- ============================================
CREATE TABLE IF NOT EXISTS `tasks` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `task_type` VARCHAR(100) NOT NULL COMMENT '任务类型',
    `status` ENUM('pending','running','completed','failed','cancelled') NOT NULL DEFAULT 'pending',
    `title` VARCHAR(500) DEFAULT NULL,
    `params` TEXT DEFAULT NULL COMMENT '任务参数 JSON',
    `result` TEXT DEFAULT NULL COMMENT '任务结果 JSON',
    `progress_current` INT NOT NULL DEFAULT 0,
    `progress_total` INT NOT NULL DEFAULT 0,
    `error_message` TEXT DEFAULT NULL,
    `worker_id` VARCHAR(100) DEFAULT NULL COMMENT '抢占此任务的 Worker ID',
    `started_at` TIMESTAMP NULL DEFAULT NULL,
    `completed_at` TIMESTAMP NULL DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_task_type` (`task_type`),
    INDEX `idx_status` (`status`),
    INDEX `idx_worker_id` (`worker_id`),
    INDEX `idx_task_type_status` (`task_type`, `status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- ============================================
-- 任务事件表
-- ============================================
CREATE TABLE IF NOT EXISTS `task_events` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `task_id` INT UNSIGNED NOT NULL,
    `event_type` ENUM('created','started','progress','completed','failed','cancelled','logged') NOT NULL,
    `event_data` TEXT DEFAULT NULL COMMENT '事件数据 JSON',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_task_id` (`task_id`),
    INDEX `idx_created_at` (`created_at`),
    CONSTRAINT `fk_events_task` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务事件表';

-- ============================================
-- 用户表
-- ============================================
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(255) NOT NULL UNIQUE,
    `password` VARCHAR(255) NOT NULL,
    `role` ENUM('admin','user') NOT NULL DEFAULT 'user',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `office` VARCHAR(500) DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 插入默认管理员用户 (密码: admin123)
INSERT IGNORE INTO `users` (`username`, `password`, `role`, `is_active`) VALUES ('admin', 'admin123', 'admin', 1);

-- ============================================
-- 定时任务表
-- ============================================
CREATE TABLE IF NOT EXISTS `schedules` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `schedule_type` ENUM('sitemap_crawl','article_crawl','keyword_search','cleanup_low_quality') NOT NULL DEFAULT 'sitemap_crawl',
    `status` ENUM('active','paused','disabled') NOT NULL DEFAULT 'active',
    `interval_minutes` INT NOT NULL DEFAULT 60,
    `max_executions` INT DEFAULT NULL,
    `execution_count` INT NOT NULL DEFAULT 0,
    `config` JSON DEFAULT NULL,
    `last_run_at` TIMESTAMP NULL DEFAULT NULL,
    `next_run_at` TIMESTAMP NULL DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_status` (`status`),
    INDEX `idx_next_run` (`next_run_at`),
    INDEX `idx_schedule_type` (`schedule_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='定时任务表';

-- ============================================
-- 搜索关键词表
-- ============================================
CREATE TABLE IF NOT EXISTS `search_keywords` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `keyword` VARCHAR(500) NOT NULL,
    `time_range` VARCHAR(50) DEFAULT 'week',
    `max_results` INT DEFAULT 50,
    `region` VARCHAR(20) DEFAULT 'kz-kk',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `search_count` INT NOT NULL DEFAULT 0,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='搜索关键词表';

-- ============================================
-- 对话表
-- ============================================
CREATE TABLE IF NOT EXISTS `conversations` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(500) DEFAULT '新对话',
    `mode` VARCHAR(50) DEFAULT 'chat',
    `web_search_enabled` TINYINT(1) NOT NULL DEFAULT 0,
    `internal_search_enabled` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话表';

-- ============================================
-- 消息表
-- ============================================
CREATE TABLE IF NOT EXISTS `messages` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `conversation_id` INT UNSIGNED NOT NULL,
    `role` VARCHAR(50) NOT NULL COMMENT 'user / assistant / system',
    `content` TEXT NOT NULL,
    `agent_state` JSON DEFAULT NULL,
    `search_results` JSON DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_conversation_id` (`conversation_id`),
    CONSTRAINT `fk_messages_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表';

-- ============================================
-- 报告模板表
-- ============================================
CREATE TABLE IF NOT EXISTS `report_templates` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `system_prompt` TEXT NOT NULL,
    `section_template` JSON DEFAULT NULL,
    `is_default` TINYINT(1) DEFAULT 0,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告模板表';

-- ============================================
-- 报告表
-- ============================================
CREATE TABLE IF NOT EXISTS `reports` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(512) NOT NULL,
    `time_range_start` TIMESTAMP NOT NULL,
    `time_range_end` TIMESTAMP NOT NULL,
    `template_id` INT UNSIGNED DEFAULT NULL,
    `custom_prompt` TEXT DEFAULT NULL,
    `language` VARCHAR(10) DEFAULT 'zh',
    `max_events` INT DEFAULT 10,
    `total_articles` INT DEFAULT 0,
    `clustered_articles` INT DEFAULT 0,
    `event_count` INT DEFAULT 0,
    `content` TEXT DEFAULT NULL,
    `sections` JSON DEFAULT NULL,
    `status` VARCHAR(20) DEFAULT 'draft',
    `agent_stage` VARCHAR(50) DEFAULT 'initializing',
    `agent_progress` INT DEFAULT 0,
    `agent_message` VARCHAR(500) DEFAULT '',
    `error_message` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `completed_at` TIMESTAMP NULL DEFAULT NULL,
    INDEX `idx_reports_status` (`status`),
    INDEX `idx_reports_created` (`created_at`),
    CONSTRAINT `fk_reports_template` FOREIGN KEY (`template_id`) REFERENCES `report_templates` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告表';

-- ============================================
-- 报告事件表
-- ============================================
CREATE TABLE IF NOT EXISTS `report_events` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `report_id` INT UNSIGNED NOT NULL,
    `event_title` VARCHAR(500) NOT NULL,
    `event_summary` TEXT DEFAULT NULL,
    `article_count` INT DEFAULT 0,
    `keywords` JSON DEFAULT NULL,
    `importance_score` DOUBLE DEFAULT 0.0,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_report_id` (`report_id`),
    CONSTRAINT `fk_events_report` FOREIGN KEY (`report_id`) REFERENCES `reports` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告事件表';

-- ============================================
-- 报告章节表
-- ============================================
CREATE TABLE IF NOT EXISTS `report_sections` (
    `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `report_id` INT UNSIGNED NOT NULL,
    `section_title` VARCHAR(500) NOT NULL,
    `section_content` TEXT DEFAULT NULL,
    `section_order` INT DEFAULT 0,
    `event_ids` JSON DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_report_id` (`report_id`),
    CONSTRAINT `fk_sections_report` FOREIGN KEY (`report_id`) REFERENCES `reports` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告章节表';

-- ============================================
-- 报告文章关联表
-- ============================================
CREATE TABLE IF NOT EXISTS `report_articles` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `report_id` INT UNSIGNED NOT NULL,
    `article_id` BIGINT UNSIGNED NOT NULL,
    `event_id` INT UNSIGNED DEFAULT NULL,
    `is_representative` TINYINT(1) DEFAULT 0,
    `citation_index` INT DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_report_id` (`report_id`),
    INDEX `idx_article_id` (`article_id`),
    CONSTRAINT `fk_ra_report` FOREIGN KEY (`report_id`) REFERENCES `reports` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_ra_article` FOREIGN KEY (`article_id`) REFERENCES `articles` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告文章关联表';

-- ============================================
-- 报告引用表
-- ============================================
CREATE TABLE IF NOT EXISTS `report_references` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `report_id` CHAR(36) NOT NULL COMMENT '报告 UUID',
    `article_id` BIGINT UNSIGNED NOT NULL,
    `citation_index` INT UNSIGNED NOT NULL,
    `context_snippet` TEXT DEFAULT NULL,
    `citation_position` INT UNSIGNED DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_report_article_index` (`report_id`, `article_id`, `citation_index`),
    INDEX `idx_report_id` (`report_id`),
    INDEX `idx_article_id` (`article_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告引用表';

-- ============================================
-- Worker 心跳表
-- ============================================
CREATE TABLE IF NOT EXISTS `worker_heartbeats` (
    `worker_id` VARCHAR(255) NOT NULL,
    `worker_type` VARCHAR(50) NOT NULL COMMENT 'scheduler/crawl/report/search/ai/api',
    `hostname` VARCHAR(255) NOT NULL,
    `pid` INT NOT NULL,
    `last_heartbeat_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`worker_id`),
    INDEX `idx_heartbeat_type` (`worker_type`),
    INDEX `idx_heartbeat_stale` (`last_heartbeat_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Worker 心跳表';
