-- ==============================================================================
-- Migration 002: Schema Stabilization and Optimization
-- ==============================================================================
-- Newssys 2.0 Database Migration
--
-- This migration implements:
-- 1. Dual status system (ArticleStatus + FetchStatus)
-- 2. Content versioning with SHA256 hash
-- 3. Retry mechanism for failed fetches
-- 4. Flexible metadata via JSON fields
-- 5. Report tracking and citation system
-- 6. Optimized composite indexes
--
-- Usage:
--   mysql -u root -p newssys < migrations/002_schema_stabilization.sql
-- ==============================================================================

USE `newssys`;

-- ==============================================================================
-- Step 1: Add new columns to crawl_sources table
-- ==============================================================================

-- Add discovery_method enum column
ALTER TABLE `crawl_sources`
ADD COLUMN `discovery_method` ENUM('sitemap', 'list', 'hybrid')
    NOT NULL DEFAULT 'sitemap'
    COMMENT 'URL 发现策略' AFTER `failure_count`;

-- Add extra_data JSON column
ALTER TABLE `crawl_sources`
ADD COLUMN `extra_data` JSON
    DEFAULT NULL
    COMMENT '额外元数据（JSON）' AFTER `discovery_method`;

-- ==============================================================================
-- Step 2: Add new columns to articles table
-- ==============================================================================

-- Add content_hash for versioning
ALTER TABLE `articles`
ADD COLUMN `content_hash` CHAR(64)
    DEFAULT NULL
    COMMENT '内容的 SHA256 哈希值，用于检测内容变化' AFTER `content`;

-- Add fetch_status enum (dual status system)
ALTER TABLE `articles`
ADD COLUMN `fetch_status` ENUM('pending', 'success', 'retry', 'failed')
    NOT NULL DEFAULT 'pending'
    COMMENT '抓取任务状态' AFTER `status`;

-- Add error_msg (new error field, preferred over error_message)
ALTER TABLE `articles`
ADD COLUMN `error_msg` TEXT
    DEFAULT NULL
    COMMENT '错误信息（新字段，优先使用）' AFTER `error_message`;

-- Add retry_count
ALTER TABLE `articles`
ADD COLUMN `retry_count` INT UNSIGNED
    NOT NULL DEFAULT 0
    COMMENT '重试次数' AFTER `synced_at`;

-- Add last_retry_at
ALTER TABLE `articles`
ADD COLUMN `last_retry_at` TIMESTAMP
    DEFAULT NULL
    COMMENT '最后重试时间' AFTER `retry_count`;

-- Add extra_data JSON column
ALTER TABLE `articles`
ADD COLUMN `extra_data` JSON
    DEFAULT NULL
    COMMENT '额外元数据（JSON）' AFTER `last_retry_at`;

-- ==============================================================================
-- Step 3: Create reports table
-- ==============================================================================

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

-- ==============================================================================
-- Step 4: Create report_references table
-- ==============================================================================

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

    CONSTRAINT `fk_references_report`
        FOREIGN KEY (`report_id`)
        REFERENCES `reports` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_references_article`
        FOREIGN KEY (`article_id`)
        REFERENCES `articles` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报告引用表';

-- ==============================================================================
-- Step 5: Add optimized indexes for high-frequency queries
-- ==============================================================================

-- Composite index: source_id + status + publish_time (for aggregator queries)
ALTER TABLE `articles`
ADD INDEX `idx_source_status_time`
    (`source_id`, `status`, `publish_time` DESC)
    COMMENT '按源、状态、时间筛选';

-- Composite index: fetch_status + retry_count (for retry queue)
ALTER TABLE `articles`
ADD INDEX `idx_fetch_status_retry`
    (`fetch_status`, `retry_count`)
    COMMENT '查找需要重试的文章';

-- Index for content hash (deduplication)
ALTER TABLE `articles`
ADD INDEX `idx_content_hash`
    (`content_hash`)
    COMMENT '内容去重';

-- Composite index: status + publish_time (for time-sorted status queries)
ALTER TABLE `articles`
ADD INDEX `idx_status_publish_time`
    (`status`, `publish_time` DESC)
    COMMENT '按状态和时间排序';

-- Index for discovery_method on crawl_sources
ALTER TABLE `crawl_sources`
ADD INDEX `idx_discovery_method`
    (`discovery_method`)
    COMMENT 'URL 发现策略';

-- ==============================================================================
-- Step 6: Data migration (sync existing data)
-- ==============================================================================

-- Migrate existing error_message to error_msg for non-null values
UPDATE `articles`
SET `error_msg` = `error_message`
WHERE `error_message` IS NOT NULL
  AND `error_msg` IS NULL;

-- Set fetch_status based on status for existing records
UPDATE `articles`
SET `fetch_status` = CASE
    WHEN `status` = 'raw' THEN 'pending'
    WHEN `status` = 'processed' THEN 'success'
    WHEN `status` = 'synced' THEN 'success'
    WHEN `status` = 'failed' THEN 'failed'
    ELSE 'pending'
END
WHERE `fetch_status` = 'pending';

-- ==============================================================================
-- Step 7: Verification queries (uncomment to verify)
-- ==============================================================================

-- Check new columns on articles table
-- SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE TABLE_SCHEMA = 'newssys' AND TABLE_NAME = 'articles'
--   AND COLUMN_NAME IN ('content_hash', 'fetch_status', 'error_msg', 'retry_count', 'last_retry_at', 'extra_data')
-- ORDER BY ORDINAL_POSITION;

-- Check new tables
-- SELECT TABLE_NAME, ENGINE, TABLE_COMMENT
-- FROM INFORMATION_SCHEMA.TABLES
-- WHERE TABLE_SCHEMA = 'newssys' AND TABLE_NAME IN ('reports', 'report_references');

-- Check new indexes
-- SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME
-- FROM INFORMATION_SCHEMA.STATISTICS
-- WHERE TABLE_SCHEMA = 'newssys' AND INDEX_NAME LIKE 'idx_%'
--   AND INDEX_NAME IN ('idx_source_status_time', 'idx_fetch_status_retry', 'idx_content_hash', 'idx_status_publish_time', 'idx_discovery_method')
-- ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- ==============================================================================
-- Migration Complete
-- ==============================================================================
