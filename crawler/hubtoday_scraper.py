#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HubToday AI Scraper
Crawls articles from https://ai.hubtoday.app/
"""

import asyncio
import json
import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy import select

from crawler.base_scraper import BaseWebScraper
from database.models import AibaseArticle
from database.db_session import get_session
from crawler import utils

logger = utils.setup_logger()

class HubTodayScraper(BaseWebScraper):
    """Scraper for HubToday AI website."""
    
    def __init__(self):
        super().__init__(
            base_url="https://ai.hubtoday.app",
            company_name="hubtoday"
        )
    
    async def get_article_list(self, page: int = 1) -> List[Dict]:
        """Get list of daily report links from HubToday."""
        try:
            # HubToday is a blog listing daily reports.
            # Page 1 is home, subsequent pages might not exist or be structured differently?
            # It seems it's a static site generator structure.
            # Let's assume just fetching the home page is enough for recent "dailies".
            
            if page > 1:
                 # TODO: Check if pagination exists, e.g. /page/2
                 # For now, only crawl home page as it lists many days
                 return []

            url = self.base_url
            logger.info(f"Fetching HubToday list: {url}")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # Find daily links
            # Links look like /2025-12/2025-12-19/
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '').strip()
                title = link.get_text(strip=True)
                
                # Filter for daily report links
                # Pattern: /YYYY-MM/YYYY-MM-DD/
                if not re.search(r'/\d{4}-\d{2}/\d{4}-\d{2}-\d{2}/?', href):
                    continue
                
                full_url = urljoin(self.base_url, href)
                
                # Extract date from URL as ID
                # /2025-12/2025-12-19/ -> 2025-12-19
                match = re.search(r'/(\d{4}-\d{2}-\d{2})/?$', href)
                if match:
                    date_str = match.group(1)
                    article_id = f"hubtoday_{date_str}"
                else:
                    continue
                
                if not title:
                    title = f"HubToday AI Daily {date_str}"

                articles.append({
                    'article_id': article_id,
                    'title': title,
                    'url': full_url,
                    'publish_date': date_str
                })
            
            # Deduplicate
            unique_articles = []
            seen = set()
            for art in articles:
                if art['article_id'] not in seen:
                    seen.add(art['article_id'])
                    unique_articles.append(art)
            
            logger.info(f"Extracted {len(unique_articles)} HubToday daily reports")
            return unique_articles
        
        except Exception as e:
            logger.error(f"Failed to get HubToday list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> List[Dict]:
        """Fetch article details and split by h3 tags."""
        try:
            logger.info(f"Fetching HubToday detail: {article_id}")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Content container
            content_elem = soup.find('article')
            if not content_elem:
                content_elem = soup.find('main')
            
            if content_elem:
                 # Clean up navigation or sidebar if inside main
                 for nav in content_elem.find_all(['nav', 'aside']):
                     nav.decompose()
            else:
                return []

            # Extract date from article_id
            try:
                date_str = article_id.replace('hubtoday_', '')
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                publish_time = int(dt.timestamp())
                publish_date = date_str
            except:
                publish_time = int(datetime.now().timestamp())
                publish_date = datetime.now().strftime('%Y-%m-%d')

            # Common fields
            base_article = {
                'article_url': url,
                'publish_time': publish_time,
                'publish_date': publish_date,
                'author': '何夕2077',
                'cover_image': soup.find('img').get('src', '') if soup.find('img') else '',
                'tags': json.dumps(['AI日报', 'AI News'], ensure_ascii=False),
                'read_count': 0,
                'like_count': 0,
                'comment_count': 0,
                'share_count': 0,
                'collect_count': 0,
                'is_original': 0,
            }

            articles = []
            h3_tags = content_elem.find_all('h3')
            
            if not h3_tags:
                # Fallback: treat whole page as one article
                title_elem = soup.find('h1')
                title = self.clean_text(title_elem.get_text()) if title_elem else ''
                content = self.clean_text(content_elem.get_text())
                
                article = base_article.copy()
                article['article_id'] = article_id
                article['title'] = title
                article['content'] = content
                article['description'] = content[:200]
                
                reference_links = self.extract_reference_links(soup, content_elem)
                article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
                
                articles.append(article)
            else:
                # Split by h3, including content before the first h3
                
                # Iterate through all children to capture everything in order
                current_title = "今日摘要" # Default for content before first h3
                current_nodes = []
                
                for child in content_elem.children:
                    if child.name == 'h3':
                        # If we have accumulated content, save it as a section
                        if current_nodes:
                            full_html = "".join(current_nodes)
                            fragment_soup = BeautifulSoup(full_html, 'html.parser')
                            content_text = self.clean_text(fragment_soup.get_text())
                            
                            if content_text:
                                # Generate ID
                                hash_object = hashlib.md5(current_title.encode('utf-8'))
                                title_hash = hash_object.hexdigest()[:8]
                                new_article_id = f"{article_id}_{title_hash}"
                                
                                article = base_article.copy()
                                article['article_id'] = new_article_id
                                article['title'] = current_title
                                article['content'] = content_text
                                article['description'] = content_text[:200]
                                
                                reference_links = self.extract_reference_links(soup, fragment_soup)
                                article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
                                
                                articles.append(article)
                        
                        # Start new section
                        current_title = self.clean_text(child.get_text())
                        current_nodes = []
                    else:
                        current_nodes.append(str(child))
                
                # Don't forget the last section
                if current_nodes and current_title:
                    full_html = "".join(current_nodes)
                    fragment_soup = BeautifulSoup(full_html, 'html.parser')
                    content_text = self.clean_text(fragment_soup.get_text())
                    
                    if content_text:
                        hash_object = hashlib.md5(current_title.encode('utf-8'))
                        title_hash = hash_object.hexdigest()[:8]
                        new_article_id = f"{article_id}_{title_hash}"
                        
                        article = base_article.copy()
                        article['article_id'] = new_article_id
                        article['title'] = current_title
                        article['content'] = content_text
                        article['description'] = content_text[:200]
                        
                        reference_links = self.extract_reference_links(soup, fragment_soup)
                        article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
                        
                        articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to get detail {article_id}: {e}")
            return []

async def save_article_to_db(article: Dict):
    """Save article to AibaseArticle table (reused for HubToday)."""
    async with get_session() as session:
        article_id = article.get('article_id')
        
        stmt = select(AibaseArticle).where(AibaseArticle.article_id == article_id)
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
            article['source_keyword'] = 'hubtoday' # Mark source
            
            valid_keys = {c.name for c in AibaseArticle.__table__.columns}
            filtered_article = {k: v for k, v in article.items() if k in valid_keys}
            
            db_article = AibaseArticle(**filtered_article)
            session.add(db_article)
            logger.info(f"Saved new article: {article_id}")

async def run_crawler(days=3):
    """Run the HubToday crawler."""
    logger.info("=" * 60)
    logger.info("🚀 HubToday Crawler Started")
    logger.info("=" * 60)
    
    start_date = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    scraper = HubTodayScraper()
    await scraper.init()
    
    try:
        articles = await scraper.get_article_list()
        
        for article_item in articles:
            try:
                # Check date - 使用日期对象比较而不是字符串比较
                article_date_str = article_item.get('publish_date')
                if article_date_str:
                    try:
                        article_date = datetime.strptime(article_date_str, '%Y-%m-%d').date()
                        if article_date < start_date.date():
                            logger.info(f"Article {article_item['article_id']} too old")
                            continue
                    except ValueError:
                        logger.warning(f"Invalid date format for article {article_item['article_id']}: {article_date_str}")
                        continue

                articles_list = await scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if not articles_list:
                    continue
                
                for article in articles_list:
                    await save_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing {article_item['article_id']}: {e}")
                continue
                
    finally:
        await scraper.close()
        logger.info("HubToday Crawler finished.")

if __name__ == "__main__":
    asyncio.run(run_crawler())

