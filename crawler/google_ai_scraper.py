#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google AI (DeepMind & Google Research) Scraper
爬取Google AI、DeepMind的研究论文和博客
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from crawler.base_scraper import BaseWebScraper
from crawler.openai_scraper import save_company_article_to_db
from crawler import utils

logger = utils.setup_logger()


class GoogleAIScraper(BaseWebScraper):
    """Google AI官网爬虫（包括DeepMind）"""
    
    def __init__(self, source: str = 'google'):
        """
        Args:
            source: 'google' for Google AI Blog, 'deepmind' for DeepMind
        """
        if source == 'deepmind':
            base_url = "https://deepmind.google"
            company_name = "deepmind"
        else:
            base_url = "https://blog.google"
            company_name = "google"
        
        super().__init__(base_url=base_url, company_name=company_name)
        self.source = source
        
        if source == 'deepmind':
            self.blog_url = "https://deepmind.google/discover/blog/"
            self.research_url = "https://deepmind.google/research/"
        else:
            self.blog_url = "https://blog.google/technology/ai/"
    
    async def get_article_list(self, page: int = 1, article_type: str = 'blog') -> List[Dict]:
        """获取文章列表"""
        try:
            if self.source == 'deepmind':
                if article_type == 'research':
                    url = self.research_url
                else:
                    url = self.blog_url
            else:
                url = self.blog_url
            
            logger.info(f"Fetching {self.company_name} {article_type} list from {url}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # Google和DeepMind都使用article标签或特定的卡片容器
            article_elements = soup.find_all(['article', 'div'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['post', 'card', 'item', 'article']))
            
            if not article_elements:
                article_elements = soup.select('a[href*="/blog/"], a[href*="/research/"], a[href*="/discover/"]')
            
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
                    
                    article_id = self.extract_article_id(url)
                    if not article_id:
                        continue
                    
                    title_elem = elem.find(['h1', 'h2', 'h3', 'h4'])
                    if not title_elem:
                        title_elem = link_elem
                    title = self.clean_text(title_elem.get_text())
                    
                    if not title or len(title) < 5:
                        continue
                    
                    if '/research/' in url:
                        determined_type = 'research'
                    else:
                        determined_type = 'blog'
                    
                    articles.append({
                        'article_id': f"{self.company_name}_{article_id}",
                        'title': title[:500],
                        'url': url,
                        'article_type': determined_type,
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} {self.company_name} articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get {self.company_name} article list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"Fetching {self.company_name} article details: {article_id}")
            
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
            
            # 内容
            content_elem = soup.find('article')
            if not content_elem:
                content_elem = soup.find('main')
            if not content_elem:
                content_elem = soup.find(['div'], class_=lambda x: x and ('content' in str(x).lower() or 'article' in str(x).lower()))
            
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
                article['description'] = article['content'][:300]
            
            # 作者
            author_elem = soup.find(['span', 'div', 'p'], class_=lambda x: x and 'author' in str(x).lower())
            if not author_elem:
                author_elem = soup.find('meta', attrs={'name': 'author'})
                article['author'] = author_elem.get('content', '') if author_elem else ('DeepMind' if self.source == 'deepmind' else 'Google AI')
            else:
                article['author'] = self.clean_text(author_elem.get_text())
            
            # 发布时间
            time_elem = soup.find('time')
            if time_elem:
                time_str = time_elem.get('datetime', '') or time_elem.get_text()
            else:
                time_elem = soup.find('meta', attrs={'property': 'article:published_time'})
                time_str = time_elem.get('content', '') if time_elem else ''
            
            article['publish_time'] = self.parse_timestamp(time_str) if time_str else utils.get_current_timestamp()
            article['publish_date'] = datetime.fromtimestamp(article['publish_time']).strftime('%Y-%m-%d')
            
            # 分类
            article['category'] = 'AI Research' if '/research/' in url else 'AI Blog'
            
            # 标签
            tag_elements = soup.find_all(['a', 'span'], class_=lambda x: x and 'tag' in str(x).lower())
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
            article['is_product'] = 1 if any(keyword in article['title'].lower() for keyword in ['gemini', 'bard', 'palm', 'product', 'launch', 'release', 'announce']) else 0
            
            return article
        
        except Exception as e:
            logger.error(f"Failed to get {self.company_name} article details {article_id}: {e}")
            return None


async def run_google_ai_crawler(days: int = 7):
    """运行Google AI爬虫"""
    logger.info("=" * 60)
    logger.info("🚀 Google AI Crawler Started")
    logger.info("=" * 60)
    
    # Google AI Blog
    google_scraper = GoogleAIScraper(source='google')
    await google_scraper.init()
    
    try:
        logger.info("Fetching Google AI blog articles...")
        articles = await google_scraper.get_article_list(article_type='blog')
        
        for article_item in articles[:15]:
            try:
                article = await google_scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing Google AI article: {e}")
                continue
    finally:
        await google_scraper.close()
    
    # DeepMind
    deepmind_scraper = GoogleAIScraper(source='deepmind')
    await deepmind_scraper.init()
    
    try:
        # DeepMind Blog
        logger.info("Fetching DeepMind blog articles...")
        blog_articles = await deepmind_scraper.get_article_list(article_type='blog')
        
        for article_item in blog_articles[:15]:
            try:
                article = await deepmind_scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing DeepMind blog article: {e}")
                continue
        
        # DeepMind Research
        logger.info("Fetching DeepMind research articles...")
        research_articles = await deepmind_scraper.get_article_list(article_type='research')
        
        for article_item in research_articles[:15]:
            try:
                article = await deepmind_scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing DeepMind research article: {e}")
                continue
        
    finally:
        await deepmind_scraper.close()
        logger.info("Google AI & DeepMind Crawler finished.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_google_ai_crawler())

