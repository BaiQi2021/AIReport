#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Companies Scraper
AI公司官网爬虫（OpenAI, Anthropic, Google, Meta, Qwen, xAI, Microsoft, NVIDIA等）
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from sqlalchemy import select

from crawler.base_scraper import BaseWebScraper
from database.models import CompanyArticle
from database.db_session import get_session
from crawler import utils

logger = utils.setup_logger()


class OpenAIScraper(BaseWebScraper):
    """OpenAI新闻爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://openai.com/news/",
            company_name="openai"
        )
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        return await get_generic_article_detail(self, article_id, url)
    
    async def get_article_list(self, article_type: str = 'news') -> List[Dict]:
        """获取文章列表"""
        try:
            url = self.base_url
            logger.info(f"Fetching OpenAI news list from {url}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # OpenAI使用特定的结构
            article_elements = soup.find_all(['article', 'a'], href=lambda x: x and '/news/' in x)
            
            logger.info(f"Found {len(article_elements)} potential article elements")
            
            for elem in article_elements[:20]:
                try:
                    if elem.name == 'a':
                        link_elem = elem
                    else:
                        link_elem = elem.find('a', href=True)
                    
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if url.startswith('/'):
                        url = 'https://openai.com' + url
                    
                    if '/news/' not in url or url == self.base_url:
                        continue
                    
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
                        'article_id': f"openai_{article_id}",
                        'title': title[:500],
                        'url': url,
                    })
                    
                except Exception as e:
                    logger.debug(f"Failed to parse element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} OpenAI articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get OpenAI article list: {e}")
            return []


class QwenScraper(BaseWebScraper):
    """Qwen研究爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://qwen.ai/research",
            company_name="qwen"
        )
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        return await get_generic_article_detail(self, article_id, url)
    
    async def get_article_list(self, article_type: str = 'research') -> List[Dict]:
        """获取文章列表"""
        try:
            logger.info(f"Fetching Qwen research list from {self.base_url}...")
            
            html = await self.fetch_page(self.base_url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # 查找文章元素
            article_elements = soup.find_all(['article', 'div', 'li'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['research', 'paper', 'publication', 'article', 'card']
            ))
            
            if not article_elements:
                article_elements = soup.find_all('a', href=lambda x: x and 'research' in str(x).lower())
            
            logger.info(f"Found {len(article_elements)} potential article elements")
            
            for elem in article_elements[:20]:
                try:
                    if elem.name == 'a':
                        link_elem = elem
                    else:
                        link_elem = elem.find('a', href=True)
                    
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if url.startswith('/'):
                        url = 'https://qwen.ai' + url
                    elif not url.startswith('http'):
                        continue
                    
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
                        'article_id': f"qwen_{article_id}",
                        'title': title[:500],
                        'url': url,
                    })
                    
                except Exception as e:
                    logger.debug(f"Failed to parse element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} Qwen articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Qwen article list: {e}")
            return []


class XAIScraper(BaseWebScraper):
    """xAI (Grok)新闻爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://x.ai/news",
            company_name="xai"
        )
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        return await get_generic_article_detail(self, article_id, url)
    
    async def get_article_list(self, article_type: str = 'news') -> List[Dict]:
        """获取文章列表"""
        try:
            logger.info(f"Fetching xAI news list from {self.base_url}...")
            
            html = await self.fetch_page(self.base_url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            article_elements = soup.find_all(['article', 'div'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['news', 'post', 'article']
            ))
            
            if not article_elements:
                article_elements = soup.find_all('a', href=lambda x: x and '/news/' in str(x))
            
            logger.info(f"Found {len(article_elements)} potential article elements")
            
            for elem in article_elements[:20]:
                try:
                    if elem.name == 'a':
                        link_elem = elem
                    else:
                        link_elem = elem.find('a', href=True)
                    
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if url.startswith('/'):
                        url = 'https://x.ai' + url
                    elif not url.startswith('http'):
                        continue
                    
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
                        'article_id': f"xai_{article_id}",
                        'title': title[:500],
                        'url': url,
                    })
                    
                except Exception as e:
                    logger.debug(f"Failed to parse element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} xAI articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get xAI article list: {e}")
            return []


class NVIDIAScraper(BaseWebScraper):
    """NVIDIA新闻爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://nvidianews.nvidia.com/",
            company_name="nvidia"
        )
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        return await get_generic_article_detail(self, article_id, url)
    
    async def get_article_list(self, article_type: str = 'news') -> List[Dict]:
        """获取文章列表"""
        try:
            logger.info(f"Fetching NVIDIA news list from {self.base_url}...")
            
            html = await self.fetch_page(self.base_url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            article_elements = soup.find_all(['article', 'div'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['news', 'article', 'post', 'item']
            ))
            
            logger.info(f"Found {len(article_elements)} potential article elements")
            
            for elem in article_elements[:20]:
                try:
                    link_elem = elem.find('a', href=True)
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if url.startswith('/'):
                        url = 'https://nvidianews.nvidia.com' + url
                    elif not url.startswith('http'):
                        continue
                    
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
                        'article_id': f"nvidia_{article_id}",
                        'title': title[:500],
                        'url': url,
                    })
                    
                except Exception as e:
                    logger.debug(f"Failed to parse element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} NVIDIA articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get NVIDIA article list: {e}")
            return []


class MicrosoftAIScraper(BaseWebScraper):
    """Microsoft AI新闻爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://news.microsoft.com/source/topics/ai/",
            company_name="microsoft"
        )
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        return await get_generic_article_detail(self, article_id, url)
    
    async def get_article_list(self, article_type: str = 'news') -> List[Dict]:
        """获取文章列表"""
        try:
            logger.info(f"Fetching Microsoft AI news list from {self.base_url}...")
            
            html = await self.fetch_page(self.base_url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            article_elements = soup.find_all(['article', 'div'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['article', 'post', 'story']
            ))
            
            logger.info(f"Found {len(article_elements)} potential article elements")
            
            for elem in article_elements[:20]:
                try:
                    link_elem = elem.find('a', href=True)
                    if not link_elem:
                        continue
                    
                    url = link_elem.get('href', '')
                    if url.startswith('/'):
                        url = 'https://news.microsoft.com' + url
                    elif not url.startswith('http'):
                        continue
                    
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
                        'article_id': f"microsoft_{article_id}",
                        'title': title[:500],
                        'url': url,
                    })
                    
                except Exception as e:
                    logger.debug(f"Failed to parse element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} Microsoft AI articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Microsoft AI article list: {e}")
            return []


# 通用文章详情获取函数
async def get_generic_article_detail(scraper: BaseWebScraper, article_id: str, url: str) -> Optional[Dict]:
    """通用文章详情获取"""
    try:
        logger.info(f"Fetching article details: {article_id}")
        
        html = await scraper.fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        article = {
            'article_id': article_id,
            'article_url': url,
            'source_keyword': scraper.company_name,
            'company': scraper.company_name,
        }
        
        # 标题
        title_elem = soup.find('h1')
        if not title_elem:
            title_elem = soup.find('title')
            article['title'] = title_elem.get_text(strip=True).split('|')[0].strip() if title_elem else ''
        else:
            article['title'] = scraper.clean_text(title_elem.get_text())
        
        # 内容
        content_elem = soup.find('article')
        if not content_elem:
            content_elem = soup.find(['div', 'main'], class_=lambda x: x and 'content' in str(x).lower())
        if not content_elem:
            content_elem = soup.find('main')
        
        article['content'] = scraper.clean_text(content_elem.get_text()) if content_elem else ''
        
        # 提取参考链接
        reference_links = scraper.extract_reference_links(soup, content_elem)
        article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
        
        # 描述
        desc_elem = soup.find('meta', attrs={'name': 'description'})
        if not desc_elem:
            desc_elem = soup.find('meta', attrs={'property': 'og:description'})
        article['description'] = desc_elem.get('content', '')[:500] if desc_elem else article['content'][:200]
        
        # 作者
        author_elem = soup.find(class_=lambda x: x and 'author' in str(x).lower())
        if not author_elem:
            author_elem = soup.find('meta', attrs={'name': 'author'})
            author_text = author_elem.get('content', scraper.company_name) if author_elem else scraper.company_name
        else:
            author_text = scraper.clean_text(author_elem.get_text())
        
        # 严格限制作者字段长度，避免提取到整段内容
        if len(author_text) > 100:  # 如果太长，说明提取错误
            author_text = scraper.company_name
        article['author'] = author_text[:255]  # 最终限制
        
        # 发布时间
        time_elem = soup.find('time')
        if not time_elem:
            time_elem = soup.find('meta', attrs={'property': 'article:published_time'})
            time_str = time_elem.get('content') if time_elem else ''
        else:
            time_str = time_elem.get('datetime', '') or time_elem.get_text(strip=True)
        
        article['publish_time'] = scraper.parse_timestamp(time_str) if time_str else utils.get_current_timestamp()
        article['publish_date'] = datetime.fromtimestamp(article['publish_time']).strftime('%Y-%m-%d')
        
        # 其他字段
        article['category'] = 'AI资讯'
        article['tags'] = ''
        article['cover_image'] = ''
        article['is_original'] = 1
        
        return article
    
    except Exception as e:
        logger.error(f"Failed to get article details {article_id}: {e}")
        return None


async def save_company_article_to_db(article: Dict):
    """保存文章到数据库"""
    async with get_session() as session:
        article_id = article.get('article_id')
        
        stmt = select(CompanyArticle).where(CompanyArticle.article_id == article_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.last_modify_ts = utils.get_current_timestamp()
            for key, value in article.items():
                if hasattr(existing, key) and key not in ['id', 'add_ts']:
                    setattr(existing, key, value)
            logger.info(f"Updated article: {article_id}")
        else:
            article['add_ts'] = utils.get_current_timestamp()
            article['last_modify_ts'] = utils.get_current_timestamp()
            
            valid_keys = {c.name for c in CompanyArticle.__table__.columns}
            filtered_article = {k: v for k, v in article.items() if k in valid_keys}
            
            db_article = CompanyArticle(**filtered_article)
            session.add(db_article)
            logger.info(f"Saved new article: {article_id}")


if __name__ == "__main__":
    async def test():
        scraper = QwenScraper()
        await scraper.init()
        
        articles = await scraper.get_article_list()
        logger.info(f"Found {len(articles)} articles")
        
        if articles:
            detail = await get_generic_article_detail(scraper, articles[0]['article_id'], articles[0]['url'])
            if detail:
                logger.info(f"Article: {detail['title']}")
        
        await scraper.close()
    
    asyncio.run(test())

