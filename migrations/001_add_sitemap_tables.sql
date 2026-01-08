-- Sitemap 表
CREATE TABLE IF NOT EXISTS sitemaps (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL UNIQUE,
    last_fetched TIMESTAMP,
    fetch_status VARCHAR(50) DEFAULT 'pending', -- pending, success, failed
    article_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 待爬文章表
CREATE TABLE IF NOT EXISTS pending_articles (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    sitemap_id INTEGER REFERENCES sitemaps(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    url_hash VARCHAR(32) NOT NULL,
    title VARCHAR(500),
    publish_time TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending', -- pending, crawling, completed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(url_hash)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_sitemaps_source_id ON sitemaps(source_id);
CREATE INDEX IF NOT EXISTS idx_sitemaps_fetch_status ON sitemaps(fetch_status);
CREATE INDEX IF NOT EXISTS idx_pending_articles_source_id ON pending_articles(source_id);
CREATE INDEX IF NOT EXISTS idx_pending_articles_sitemap_id ON pending_articles(sitemap_id);
CREATE INDEX IF NOT EXISTS idx_pending_articles_status ON pending_articles(status);
CREATE INDEX IF NOT EXISTS idx_pending_articles_url_hash ON pending_articles(url_hash);
