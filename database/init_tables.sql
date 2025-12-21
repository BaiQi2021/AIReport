-- ===============================
-- AIReport 数据库表结构
-- 量子位(QbitAI)爬虫相关表
-- ===============================

-- ----------------------------
-- Table structure for qbitai_article
-- 量子位文章表：存储从量子位网站爬取的AI相关文章
-- ----------------------------
DROP TABLE IF EXISTS `qbitai_article`;

CREATE TABLE `qbitai_article` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
    `article_id` varchar(255) NOT NULL COMMENT '文章唯一ID',
    `title` text NOT NULL COMMENT '文章标题',
    `description` text COMMENT '文章描述/摘要',
    `content` longtext COMMENT '文章内容',
    `article_url` text NOT NULL COMMENT '文章链接',
    `author` varchar(255) DEFAULT NULL COMMENT '文章作者',
    `publish_time` bigint DEFAULT NULL COMMENT '发布时间戳',
    `publish_date` varchar(10) DEFAULT NULL COMMENT '发布日期(YYYY-MM-DD)',
    `read_count` int DEFAULT 0 COMMENT '阅读数',
    `like_count` int DEFAULT 0 COMMENT '点赞数',
    `comment_count` int DEFAULT 0 COMMENT '评论数',
    `share_count` int DEFAULT 0 COMMENT '分享数',
    `collect_count` int DEFAULT 0 COMMENT '收藏数',
    `category` varchar(100) DEFAULT NULL COMMENT '文章分类',
    `tags` text COMMENT '文章标签(JSON格式)',
    `cover_image` varchar(512) DEFAULT NULL COMMENT '文章封面图片URL',
    `source_keyword` varchar(255) DEFAULT '' COMMENT '来源关键词',
    `is_original` int DEFAULT 1 COMMENT '是否原创(1-是, 0-否)',
    `reference_links` text COMMENT '文章中的参考链接(JSON格式)',
    `add_ts` bigint NOT NULL COMMENT '记录添加时间戳',
    `last_modify_ts` bigint NOT NULL COMMENT '记录最后修改时间戳',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_qbitai_article_unique` (`article_id`),
    KEY `idx_qbitai_article_date` (`publish_date`),
    KEY `idx_qbitai_article_time` (`publish_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='量子位文章表';

-- ===============================
-- 索引优化
-- ===============================
-- 为常用查询优化添加复合索引
CREATE INDEX `idx_article_date_category` ON `qbitai_article` (`publish_date`, `category`);

-- ----------------------------
-- Table structure for jiqizhixin_article
-- 机器之心文章表：存储从机器之心网站爬取的AI相关文章
-- ----------------------------
DROP TABLE IF EXISTS `jiqizhixin_article`;

CREATE TABLE `jiqizhixin_article` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
    `article_id` varchar(255) NOT NULL COMMENT '文章唯一ID',
    `title` text NOT NULL COMMENT '文章标题',
    `description` text COMMENT '文章描述/摘要',
    `content` longtext COMMENT '文章内容',
    `article_url` text NOT NULL COMMENT '文章链接',
    `author` varchar(255) DEFAULT NULL COMMENT '文章作者',
    `publish_time` bigint DEFAULT NULL COMMENT '发布时间戳',
    `publish_date` varchar(10) DEFAULT NULL COMMENT '发布日期(YYYY-MM-DD)',
    `read_count` int DEFAULT 0 COMMENT '阅读数',
    `like_count` int DEFAULT 0 COMMENT '点赞数',
    `comment_count` int DEFAULT 0 COMMENT '评论数',
    `share_count` int DEFAULT 0 COMMENT '分享数',
    `collect_count` int DEFAULT 0 COMMENT '收藏数',
    `category` varchar(100) DEFAULT NULL COMMENT '文章分类',
    `tags` text COMMENT '文章标签(JSON格式)',
    `cover_image` varchar(512) DEFAULT NULL COMMENT '文章封面图片URL',
    `source_keyword` varchar(255) DEFAULT '' COMMENT '来源关键词',
    `is_original` int DEFAULT 1 COMMENT '是否原创(1-是, 0-否)',
    `reference_links` text COMMENT '文章中的参考链接(JSON格式)',
    `add_ts` bigint NOT NULL COMMENT '记录添加时间戳',
    `last_modify_ts` bigint NOT NULL COMMENT '记录最后修改时间戳',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_jiqizhixin_article_unique` (`article_id`),
    KEY `idx_jiqizhixin_article_date` (`publish_date`),
    KEY `idx_jiqizhixin_article_time` (`publish_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='机器之心文章表';

-- 为机器之心文章表添加复合索引
CREATE INDEX `idx_jiqizhixin_article_date_category` ON `jiqizhixin_article` (`publish_date`, `category`);

-- ===============================
-- 数据库配置说明
-- ===============================
-- 
-- 本SQL文件支持MySQL数据库。
-- 
-- 使用方法：
-- 1. 确保已创建数据库（如: CREATE DATABASE ai_report CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;）
-- 2. 选择数据库：USE ai_report;
-- 3. 执行本SQL文件：source /path/to/init_tables.sql;
--
-- 或使用命令行：
-- mysql -u root -p ai_report < database/init_tables.sql
--
-- 注意：
-- - 表结构与 SQLAlchemy 模型 (database/models.py) 保持一致
-- - publish_date 使用 varchar(10) 存储日期字符串，兼容 SQLAlchemy String(10)
-- - 外键约束确保数据完整性
-- 

