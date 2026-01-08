-- Newssys 2.0 数据库建表语句（稳定化版本）
-- MySQL 8.0 兼容

-- 创建数据库（如果不存在）
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
    `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用（1: 启用, 0: 禁用）',
    `crawl_interval` INT UNSIGNED NOT NULL DEFAULT 3600 COMMENT '爬取间隔（秒）',

    -- Robots.txt 相关
    `robots_status` ENUM('pending', 'compliant', 'restricted', 'not_found', 'error') NOT NULL DEFAULT 'pending' COMMENT 'Robots.txt 状态',
    `crawl_delay` INT UNSIGNED DEFAULT NULL COMMENT 'Robots.txt 指定的抓取延迟（秒）',
    `robots_fetched_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Robots.txt 最后获取时间',

    -- Sitemap 相关
    `sitemap_url` VARCHAR(2048) DEFAULT NULL COMMENT '主 Sitemap URL',
    `sitemap_last_fetched` TIMESTAMP NULL DEFAULT NULL COMMENT 'Sitemap 最后获取时间',
    `sitemap_entry_count` INT UNSIGNED DEFAULT NULL COMMENT 'Sitemap 条目数量',

    -- 统计信息
    `last_crawled_at` TIMESTAMP NULL DEFAULT NULL COMMENT '最后爬取时间',
    `success_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '成功爬取次数',
    `failure_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '失败爬取次数',
    `last_error` TEXT DEFAULT NULL COMMENT '最后错误信息',

    -- 发现策略
    `discovery_method` ENUM('sitemap', 'list', 'hybrid') NOT NULL DEFAULT 'sitemap' COMMENT 'URL 发现策略',

    -- 灵活元数据
    `extra_data` JSON DEFAULT NULL COMMENT '额外元数据（JSON）',

    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY `uk_site_name` (`site_name`),
    INDEX `idx_enabled` (`enabled`),
    INDEX `idx_discovery_method` (`discovery_method`),
    INDEX `idx_robots_status` (`robots_status`),
    INDEX `idx_enabled_last_crawled` (`enabled`, `last_crawled_at`) COMMENT '用于查询待爬取的源'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爬虫源配置表';

-- ============================================
-- 文章表（稳定化版本）
-- ============================================
CREATE TABLE IF NOT EXISTS `articles` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '文章 ID',
    `url_hash` CHAR(32) NOT NULL COMMENT 'URL 的 MD5 哈希值，用于去重',
    `url` VARCHAR(2048) NOT NULL COMMENT '文章 URL',
    `title` VARCHAR(512) NOT NULL COMMENT '文章标题',
    `content` TEXT COMMENT '文章内容',

    -- 内容版本化
    `content_hash` CHAR(64) DEFAULT NULL COMMENT '内容的 SHA256 哈希值，用于检测内容变化',

    `publish_time` TIMESTAMP NULL DEFAULT NULL COMMENT '发布时间',
    `author` VARCHAR(255) DEFAULT NULL COMMENT '作者',
    `source_id` INT UNSIGNED NOT NULL COMMENT '爬虫源 ID',

    -- 双重状态
    `status` ENUM('raw', 'processed', 'synced', 'failed') NOT NULL DEFAULT 'raw' COMMENT '文章语义状态',
    `fetch_status` ENUM('pending', 'success', 'retry', 'failed') NOT NULL DEFAULT 'pending' COMMENT '抓取任务状态',

    -- 错误信息
    `error_message` TEXT COMMENT '错误信息（兼容旧字段）',
    `error_msg` TEXT COMMENT '错误信息（新字段，优先使用）',

    `crawled_at` TIMESTAMP NULL DEFAULT NULL COMMENT '爬取时间',
    `processed_at` TIMESTAMP NULL DEFAULT NULL COMMENT '处理时间',
    `synced_at` TIMESTAMP NULL DEFAULT NULL COMMENT '同步时间',

    -- 重试机制
    `retry_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '重试次数',
    `last_retry_at` TIMESTAMP NULL DEFAULT NULL COMMENT '最后重试时间',

    -- 灵活元数据
    `extra_data` JSON DEFAULT NULL COMMENT '额外元数据（JSON）',

    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY `uk_url_hash` (`url_hash`),
    INDEX `idx_source_id` (`source_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_fetch_status` (`fetch_status`),
    INDEX `idx_publish_time` (`publish_time`),
    INDEX `idx_created_at` (`created_at`),

    -- 复合索引（优化高频查询）
    INDEX `idx_source_status_time` (`source_id`, `status`, `publish_time` DESC) COMMENT '按源、状态、时间筛选',
    INDEX `idx_fetch_status_retry` (`fetch_status`, `retry_count`) COMMENT '查找需要重试的文章',
    INDEX `idx_content_hash` (`content_hash`) COMMENT '内容去重',
    INDEX `idx_status_publish_time` (`status`, `publish_time` DESC) COMMENT '按状态和时间排序',

    CONSTRAINT `fk_articles_source` FOREIGN KEY (`source_id`) REFERENCES `crawl_sources` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章表';

-- 创建全文索引（可选，用于全文搜索）
-- ALTER TABLE `articles` ADD FULLTEXT INDEX `ft_title_content` (`title`, `content`) WITH PARSER ngram;

-- ============================================
-- 报告元数据表
-- ============================================
CREATE TABLE IF NOT EXISTS `reports` (
    `id` CHAR(36) NOT NULL COMMENT '报告 ID（UUID）',
    `title` VARCHAR(512) NOT NULL COMMENT '报告标题',
    `template_id` VARCHAR(100) DEFAULT NULL COMMENT '使用的模板 ID',
    `time_range` VARCHAR(50) DEFAULT NULL COMMENT '时间范围（如 week, month）',
    `article_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '引用的文章数量',
    `generated_at` TIMESTAMP NULL DEFAULT NULL COMMENT '生成时间',
    `status` ENUM('draft', 'published', 'archived') NOT NULL DEFAULT 'draft' COMMENT '报告状态',
    `extra_data` JSON DEFAULT NULL COMMENT '额外元数据',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (`id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_template_id` (`template_id`),
    INDEX `idx_generated_at` (`generated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告元数据表';

-- ============================================
-- 报告引用表
-- ============================================
CREATE TABLE IF NOT EXISTS `report_references` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT '引用 ID',
    `report_id` CHAR(36) NOT NULL COMMENT '报告 ID（UUID）',
    `article_id` BIGINT UNSIGNED NOT NULL COMMENT '文章 ID',
    `citation_index` INT UNSIGNED NOT NULL COMMENT '引用序号（如 1, 2, 3...）',
    `context_snippet` TEXT DEFAULT NULL COMMENT 'AI 引用时的上下文片段',
    `citation_position` INT UNSIGNED DEFAULT NULL COMMENT '在报告中的位置',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY `uk_report_article_index` (`report_id`, `article_id`, `citation_index`),
    INDEX `idx_report_id` (`report_id`),
    INDEX `idx_article_id` (`article_id`),

    CONSTRAINT `fk_references_report` FOREIGN KEY (`report_id`) REFERENCES `reports` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_references_article` FOREIGN KEY (`article_id`) REFERENCES `articles` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告引用表';

-- ============================================
-- 插入示例数据
-- ============================================
INSERT INTO `crawl_sources` (`site_name`, `base_url`, `parser_config`, `enabled`, `crawl_interval`)
VALUES (
    '示例新闻源',
    'https://example.com',
    JSON_OBJECT(
        'title_selector', 'h1.article-title',
        'content_selector', 'div.article-content',
        'publish_time_selector', 'time.publish-time',
        'author_selector', 'span.author-name',
        'list_selector', 'div.article-list',
        'url_selector', 'a.article-link',
        'encoding', 'utf-8'
    ),
    0,
    3600
) ON DUPLICATE KEY UPDATE `site_name` = `site_name`;
