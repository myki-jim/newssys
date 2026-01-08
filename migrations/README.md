# Database Migrations

This directory contains Alembic-style database migrations for Newssys 2.0.

## Structure

```
migrations/
├── README.md                           # This file
├── 001_initial_schema.sql              # Initial schema (deprecated, use schema.sql)
└── 002_schema_stabilization.{py,sql}   # Schema stabilization migration
```

## Migration 002: Schema Stabilization and Optimization

### Overview

This migration implements the following enhancements:

1. **Dual Status System**
   - `ArticleStatus` (semantic): raw, processed, synced, failed
   - `FetchStatus` (technical): pending, success, retry, failed

2. **Content Versioning**
   - `content_hash`: SHA256 hash for detecting content changes

3. **Retry Mechanism**
   - `retry_count`: Number of retry attempts
   - `last_retry_at`: Timestamp of last retry

4. **Flexible Metadata**
   - `extra_data`: JSON field for extensibility

5. **Report System**
   - `reports`: Report metadata
   - `report_references`: Citation tracking with context snippets

6. **Optimized Indexes**
   - `idx_source_status_time`: For aggregator queries
   - `idx_fetch_status_retry`: For retry queue
   - `idx_content_hash`: For deduplication
   - `idx_status_publish_time`: For time-sorted queries

### Usage

#### Option 1: Direct SQL Execution (Recommended)

```bash
mysql -u root -p newssys < migrations/002_schema_stabilization.sql
```

#### Option 2: Python Migration Script

```bash
# Apply migration
python migrations/002_schema_stabilization.py upgrade

# Rollback migration
python migrations/002_schema_stabilization.py downgrade

# Validate migration
python migrations/002_schema_stabilization.py validate
```

### Verification

After running the migration, verify the changes:

```sql
-- Check new columns
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'newssys'
  AND TABLE_NAME = 'articles'
  AND COLUMN_NAME IN ('content_hash', 'fetch_status', 'error_msg', 'retry_count', 'last_retry_at', 'extra_data')
ORDER BY ORDINAL_POSITION;

-- Check new tables
SELECT TABLE_NAME, ENGINE, TABLE_COMMENT
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'newssys'
  AND TABLE_NAME IN ('reports', 'report_references');

-- Check new indexes
SELECT TABLE_NAME, INDEX_NAME, GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS columns
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = 'newssys'
  AND INDEX_NAME IN ('idx_source_status_time', 'idx_fetch_status_retry', 'idx_content_hash', 'idx_status_publish_time', 'idx_discovery_method')
GROUP BY TABLE_NAME, INDEX_NAME;
```

### Rollback

If you need to rollback this migration:

```sql
-- Drop indexes
ALTER TABLE `articles` DROP INDEX `idx_status_publish_time`;
ALTER TABLE `articles` DROP INDEX `idx_content_hash`;
ALTER TABLE `articles` DROP INDEX `idx_fetch_status_retry`;
ALTER TABLE `articles` DROP INDEX `idx_source_status_time`;
ALTER TABLE `crawl_sources` DROP INDEX `idx_discovery_method`;

-- Drop tables
DROP TABLE IF EXISTS `report_references`;
DROP TABLE IF EXISTS `reports`;

-- Drop columns
ALTER TABLE `articles` DROP COLUMN `extra_data`;
ALTER TABLE `articles` DROP COLUMN `last_retry_at`;
ALTER TABLE `articles` DROP COLUMN `retry_count`;
ALTER TABLE `articles` DROP COLUMN `error_msg`;
ALTER TABLE `articles` DROP COLUMN `fetch_status`;
ALTER TABLE `articles` DROP COLUMN `content_hash`;
ALTER TABLE `crawl_sources` DROP COLUMN `extra_data`;
ALTER TABLE `crawl_sources` DROP COLUMN `discovery_method`;
```

## Best Practices

1. **Always backup before migrating**:
   ```bash
   mysqldump -u root -p newssys > backup_before_002.sql
   ```

2. **Test on staging first**: Never run migrations on production without testing

3. **Check for conflicts**: If you have existing data, the migration handles it safely

4. **Monitor performance**: New indexes may affect write performance

## Migration History

| ID | Description | Date |
|----|-------------|------|
| 001 | Initial schema | - |
| 002 | Schema stabilization and optimization | 2026-01-06 |
