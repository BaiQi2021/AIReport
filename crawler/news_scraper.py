#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI News Sites Scraper (机器之心)
爬取AI新闻网站的资讯
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from sqlalchemy import select

from crawler.base_scraper import BaseWebScraper
from database.models import QbitaiArticle
from database.db_session import get_session
from crawler import utils

logger = utils.setup_logger()


class JiqizhixinScraper(BaseWebScraper):
    """机器之心爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://www.jiqizhixin.com",
            company_name="jiqizhixin"
        )
    
    async def get_article_list(self, page: int = 1) -> List[Dict]:
        """获取文章列表"""
        try:
            if page == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}?page={page}"
            
            logger.info(f"Fetching Jiqizhixin article list page {page}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # 机器之心的文章通常在特定的容器中
            article_elements = soup.find_all(['article', 'div'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['article', 'item', 'post', 'card']))
            
            if not article_elements:
                article_elements = soup.select('a[href*="/article/"]')
            
            logger.info(f"Found {len(article_elements)} potential article elements")
            
            for elem in article_elements[:30]:
                try:
                    if elem.name == 'a':
                        link_elem = elem
                    else:
                        link_elem = elem.find('a', href=True)
                    
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if not url:
                        continue
                    
                    if url.startswith('/'):
                        url = self.base_url + url
                    elif not url.startswith('http'):
                        continue
                    
                    # 过滤逻辑放宽，并在日志中记录
                    if 'jiqizhixin.com' not in url:
                        continue
                    
                    # 如果是 pro 域名，暂时允许，后续在详情页处理
                    if 'pro.jiqizhixin.com' in url:
                        logger.debug(f"Found PRO link: {url}")
                        
                    article_id = self.extract_article_id(url)
                    if not article_id:
                        continue
                    
                    title_elem = elem.find(['h1', 'h2', 'h3', 'h4'])
                    if not title_elem:
                        title_elem = link_elem
                    title = self.clean_text(title_elem.get_text())
                    
                    if not title or len(title) < 5:
                        continue
                    
                    articles.append({
                        'article_id': f"jiqizhixin_{article_id}",
                        'title': title[:500],
                        'url': url,
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue
            
            logger.info(f"Page {page}: Extracted {len(articles)} Jiqizhixin articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Jiqizhixin article list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"Fetching Jiqizhixin article details: {article_id}")
            
            html = await self.fetch_page(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            article = {
                'article_id': article_id,
                'article_url': url,
            }
            
            # 标题
            title_elem = soup.find('h1')
            if not title_elem:
                title_elem = soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    article['title'] = title_text.split('|')[0].strip()
                else:
                    article['title'] = ''
            else:
                article['title'] = self.clean_text(title_elem.get_text())
            
            # 内容
            content_elem = soup.find(['article', 'div'], class_=lambda x: x and ('content' in str(x).lower() or 'article' in str(x).lower()))
            if not content_elem:
                content_elem = soup.find('main')
            
            article['content'] = self.clean_text(content_elem.get_text()) if content_elem else ''
            
            # 提取参考链接
            reference_links = self.extract_reference_links(soup, content_elem)
            article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
            
            # 描述
            desc_elem = soup.find('meta', attrs={'name': 'description'})
            if not desc_elem:
                desc_elem = soup.find('meta', attrs={'property': 'og:description'})
            if desc_elem:
                article['description'] = desc_elem.get('content', '')
            else:
                article['description'] = article['content'][:200]
            
            # 作者
            author_elem = soup.find(class_=lambda x: x and 'author' in str(x).lower())
            article['author'] = self.clean_text(author_elem.get_text()) if author_elem else '机器之心'
            
            # 发布时间
            time_elem = soup.find(['time', 'span'], class_=lambda x: x and 'time' in str(x).lower())
            if not time_elem:
                time_elem = soup.find('meta', attrs={'property': 'article:published_time'})
                time_str = time_elem.get('content') if time_elem else ''
            else:
                time_str = time_elem.get_text(strip=True) if time_elem.name != 'meta' else time_elem.get('content')
            
            article['publish_time'] = self.parse_timestamp(time_str) if time_str else utils.get_current_timestamp()
            article['publish_date'] = datetime.fromtimestamp(article['publish_time']).strftime('%Y-%m-%d')
            
            # 分类
            cat_elem = soup.find(class_=lambda x: x and 'category' in str(x).lower())
            article['category'] = self.clean_text(cat_elem.get_text()) if cat_elem else 'AI资讯'
            
            # 标签
            tags = []
            for tag_elem in soup.find_all(class_=lambda x: x and 'tag' in str(x).lower()):
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
            
            # 其他字段
            article['read_count'] = 0
            article['like_count'] = 0
            article['comment_count'] = 0
            article['share_count'] = 0
            article['collect_count'] = 0
            article['is_original'] = 0
            
            return article
        
        except Exception as e:
            logger.error(f"Failed to get Jiqizhixin article details {article_id}: {e}")
            return None


async def save_news_article_to_db(article: Dict):
    """保存新闻文章到数据库（使用QbitaiArticle表）"""
    async with get_session() as session:
        article_id = article.get('article_id')
        
        stmt = select(QbitaiArticle).where(QbitaiArticle.article_id == article_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.last_modify_ts = utils.get_current_timestamp()
            for key, value in article.items():
                if hasattr(existing, key) and key not in ['id', 'add_ts']:
                    setattr(existing, key, value)
            logger.info(f"Updated news article: {article_id}")
        else:
            article['add_ts'] = utils.get_current_timestamp()
            article['last_modify_ts'] = utils.get_current_timestamp()
            
            valid_keys = {c.name for c in QbitaiArticle.__table__.columns}
            filtered_article = {k: v for k, v in article.items() if k in valid_keys}
            
            db_article = QbitaiArticle(**filtered_article)
            session.add(db_article)
            logger.info(f"Saved new news article: {article_id}")


async def run_jiqizhixin_crawler(days: int = 7):
    """运行机器之心爬虫"""
    logger.info("=" * 60)
    logger.info("🚀 Jiqizhixin Crawler Started")
    logger.info("=" * 60)
    
    start_date = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    logger.info(f"Date range: {start_date.date()} to {datetime.now().date()}")
    
    scraper = JiqizhixinScraper()
    await scraper.init()
    
    try:
        page = 1
        max_pages = 5
        
        while page <= max_pages:
            articles = await scraper.get_article_list(page=page)
            if not articles:
                break
            
            for article_item in articles:
                try:
                    article = await scraper.get_article_detail(
                        article_item['article_id'],
                        article_item['url']
                    )
                    
                    if not article:
                        continue
                    
                    # 检查日期
                    article_date = article.get('publish_date')
                    if article_date < str(start_date.date()):
                        logger.info(f"Article {article['article_id']} is out of date range.")
                        continue
                    
                    await save_news_article_to_db(article)
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing Jiqizhixin article: {e}")
                    continue
            
            page += 1
            await asyncio.sleep(3)
        
    finally:
        await scraper.close()
        logger.info("Jiqizhixin Crawler finished.")


if __name__ == "__main__":
    asyncio.run(run_jiqizhixin_crawler())
