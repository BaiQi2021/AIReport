#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Research & News Scraper
爬取OpenAI官网的研究论文和新闻
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from sqlalchemy import select

from crawler.base_scraper import BaseWebScraper
from database.models import CompanyArticle
from database.db_session import get_session
from crawler import utils

logger = utils.setup_logger()


class OpenAIScraper(BaseWebScraper):
    """OpenAI官网爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://openai.com",
            company_name="openai"
        )
        # OpenAI的博客和研究页面
        self.blog_url = "https://openai.com/blog"
        self.research_url = "https://openai.com/research"
    
    async def get_article_list(self, page: int = 1, article_type: str = 'blog') -> List[Dict]:
        """获取文章列表"""
        try:
            if article_type == 'blog':
                url = self.blog_url
            elif article_type == 'research':
                url = self.research_url
            else:
                url = self.blog_url
            
            logger.info(f"Fetching OpenAI {article_type} list from {url}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # OpenAI网站使用动态加载，这里尝试多种选择器
            # 通常文章会在article标签或特定class中
            article_elements = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in x.lower() or 'card' in x.lower() or 'item' in x.lower()))
            
            if not article_elements:
                # 备选方案：查找所有包含链接的容器
                article_elements = soup.select('a[href*="/research/"], a[href*="/blog/"]')
            
            logger.info(f"Found {len(article_elements)} potential article elements")
            
            for elem in article_elements[:30]:
                try:
                    # 获取链接
                    if elem.name == 'a':
                        link_elem = elem
                    else:
                        link_elem = elem.find('a', href=True)
                    
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if not url:
                        continue
                    
                    # 补全URL
                    if url.startswith('/'):
                        url = self.base_url + url
                    elif not url.startswith('http'):
                        continue
                    
                    # 提取文章ID
                    article_id = self.extract_article_id(url)
                    if not article_id:
                        continue
                    
                    # 获取标题
                    title_elem = elem.find(['h1', 'h2', 'h3', 'h4'])
                    if not title_elem:
                        title_elem = link_elem
                    title = self.clean_text(title_elem.get_text())
                    
                    if not title or len(title) < 5:
                        continue
                    
                    # 确定文章类型
                    if '/research/' in url:
                        determined_type = 'research'
                    elif '/blog/' in url:
                        determined_type = 'blog'
                    else:
                        determined_type = article_type
                    
                    articles.append({
                        'article_id': f"openai_{article_id}",
                        'title': title[:500],
                        'url': url,
                        'article_type': determined_type,
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} OpenAI articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get OpenAI article list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"Fetching OpenAI article details: {article_id}")
            
            html = await self.fetch_page(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            article = {
                'article_id': article_id,
                'article_url': url,
                'company': self.company_name,
            }
            
            # 标题
            title_elem = soup.find('h1')
            if not title_elem:
                title_elem = soup.find('title')
            article['title'] = self.clean_text(title_elem.get_text()) if title_elem else ''
            
            # 内容 - OpenAI通常使用article标签或main标签
            content_elem = soup.find('article')
            if not content_elem:
                content_elem = soup.find('main')
            if not content_elem:
                content_elem = soup.find(['div'], class_=lambda x: x and ('content' in x.lower() or 'article' in x.lower()))
            
            article['content'] = self.clean_text(content_elem.get_text()) if content_elem else ''
            
            # 提取参考链接
            reference_links = self.extract_reference_links(soup, content_elem)
            article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
            
            # 描述/摘要
            desc_elem = soup.find('meta', attrs={'name': 'description'})
            if not desc_elem:
                desc_elem = soup.find('meta', attrs={'property': 'og:description'})
            if desc_elem:
                article['description'] = desc_elem.get('content', '')
            else:
                article['description'] = article['content'][:300]
            
            # 作者
            author_elem = soup.find(['span', 'div', 'p'], class_=lambda x: x and 'author' in x.lower())
            if not author_elem:
                author_elem = soup.find('meta', attrs={'name': 'author'})
                article['author'] = author_elem.get('content', '') if author_elem else 'OpenAI'
            else:
                article['author'] = self.clean_text(author_elem.get_text())
            
            # 发布时间
            time_elem = soup.find('time')
            if time_elem:
                time_str = time_elem.get('datetime', '') or time_elem.get_text()
            else:
                time_elem = soup.find('meta', attrs={'property': 'article:published_time'})
                time_str = time_elem.get('content', '') if time_elem else ''
            
            if not time_str:
                logger.warning(f"Skip article {article_id}: missing publish time.")
                return None
            publish_ts = self.parse_timestamp(time_str)
            if publish_ts is None:
                logger.warning(f"Skip article {article_id}: cannot parse publish time: {time_str}")
                return None
            article['publish_time'] = publish_ts
            article['publish_date'] = datetime.fromtimestamp(publish_ts).strftime('%Y-%m-%d')
            
            # 分类和标签
            article['category'] = 'AI Research' if '/research/' in url else 'AI News'
            
            # 标签
            tag_elements = soup.find_all(['a', 'span'], class_=lambda x: x and 'tag' in x.lower())
            tags = []
            for tag_elem in tag_elements:
                tag_text = self.clean_text(tag_elem.get_text())
                if tag_text and len(tag_text) < 50:
                    tags.append(tag_text)
            article['tags'] = json.dumps(tags, ensure_ascii=False) if tags else ''
            
            # 封面图片
            img_elem = soup.find('meta', attrs={'property': 'og:image'})
            if img_elem:
                article['cover_image'] = img_elem.get('content', '')
            else:
                img_elem = soup.find('img')
                article['cover_image'] = img_elem.get('src', '') if img_elem else ''
            
            # 文章类型判断
            article['article_type'] = 'research' if '/research/' in url else 'blog'
            article['is_research'] = 1 if article['article_type'] == 'research' else 0
            article['is_product'] = 1 if any(keyword in article['title'].lower() for keyword in ['gpt', 'dall-e', 'whisper', 'api', 'product', 'launch', 'release']) else 0
            
            return article
        
        except Exception as e:
            logger.error(f"Failed to get OpenAI article details {article_id}: {e}")
            return None


async def save_company_article_to_db(article: Dict):
    """保存公司文章到数据库"""
    async with get_session() as session:
        article_id = article.get('article_id')
        
        stmt = select(CompanyArticle).where(CompanyArticle.article_id == article_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        # 字段长度限制映射（根据数据库模型定义）
        field_length_limits = {
            'article_id': 255,
            'company': 100,
            'author': 255,
            'publish_date': 10,
            'category': 100,
            'cover_image': 512,
            'article_type': 50,
        }
        
        def truncate_field(key: str, value):
            """截断字段值到指定长度"""
            if key in field_length_limits and value is not None:
                if isinstance(value, str):
                    max_length = field_length_limits[key]
                    if len(value) > max_length:
                        return value[:max_length]
            return value
        
        if existing:
            existing.last_modify_ts = utils.get_current_timestamp()
            for key, value in article.items():
                if hasattr(existing, key) and key not in ['id', 'add_ts']:
                    truncated_value = truncate_field(key, value)
                    setattr(existing, key, truncated_value)
            logger.info(f"Updated company article: {article_id}")
        else:
            article['add_ts'] = utils.get_current_timestamp()
            article['last_modify_ts'] = utils.get_current_timestamp()
            
            valid_keys = {c.name for c in CompanyArticle.__table__.columns}
            filtered_article = {}
            for k, v in article.items():
                if k in valid_keys:
                    filtered_article[k] = truncate_field(k, v)
            
            db_article = CompanyArticle(**filtered_article)
            session.add(db_article)
            logger.info(f"Saved new company article: {article_id}")


async def run_openai_crawler(days: int = 7):
    """运行OpenAI爬虫"""
    logger.info("=" * 60)
    logger.info("🚀 OpenAI Crawler Started")
    logger.info("=" * 60)
    
    scraper = OpenAIScraper()
    await scraper.init()
    
    blog_saved_count = 0
    research_saved_count = 0
    blog_fetch_failed = False
    research_fetch_failed = False
    
    try:
        # 爬取博客文章
        logger.info("Fetching OpenAI blog articles...")
        blog_articles = await scraper.get_article_list(article_type='blog')
        
        if not blog_articles:
            logger.warning("⚠️  OpenAI blog: Failed to fetch article list (may be blocked or page structure changed)")
            blog_fetch_failed = True
        else:
            logger.info(f"Found {len(blog_articles)} blog articles")
            for article_item in blog_articles[:20]:  # 限制数量
                try:
                    article = await scraper.get_article_detail(
                        article_item['article_id'],
                        article_item['url']
                    )
                    
                    if article:
                        await save_company_article_to_db(article)
                        blog_saved_count += 1
                    
                    await asyncio.sleep(2)  # 礼貌延迟
                    
                except Exception as e:
                    logger.error(f"Error processing OpenAI blog article: {e}")
                    continue
        
        # 爬取研究文章
        logger.info("Fetching OpenAI research articles...")
        research_articles = await scraper.get_article_list(article_type='research')
        
        if not research_articles:
            logger.warning("⚠️  OpenAI research: Failed to fetch article list (may be blocked or page structure changed)")
            research_fetch_failed = True
        else:
            logger.info(f"Found {len(research_articles)} research articles")
            for article_item in research_articles[:20]:  # 限制数量
                try:
                    article = await scraper.get_article_detail(
                        article_item['article_id'],
                        article_item['url']
                    )
                    
                    if article:
                        await save_company_article_to_db(article)
                        research_saved_count += 1
                    
                    await asyncio.sleep(2)  # 礼貌延迟
                    
                except Exception as e:
                    logger.error(f"Error processing OpenAI research article: {e}")
                    continue
        
        # 总结统计
        total_saved = blog_saved_count + research_saved_count
        if blog_fetch_failed and research_fetch_failed:
            logger.warning("⚠️  OpenAI Crawler: Both blog and research pages failed to fetch. No articles saved.")
        elif blog_fetch_failed or research_fetch_failed:
            logger.warning(f"⚠️  OpenAI Crawler: Partial failure. Saved {total_saved} articles (blog: {blog_saved_count}, research: {research_saved_count})")
        else:
            logger.info(f"✅ OpenAI Crawler: Successfully saved {total_saved} articles (blog: {blog_saved_count}, research: {research_saved_count})")
        
    finally:
        await scraper.close()
        logger.info("OpenAI Crawler finished.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_openai_crawler())

