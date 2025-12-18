#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
China AI Companies Scraper
爬取国内主要AI公司（百度、阿里、智谱AI等）的官网新闻和研究
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from crawler.base_scraper import BaseWebScraper
from crawler.openai_scraper import save_company_article_to_db
from crawler import utils

logger = utils.setup_logger()


class ZhipuAIScraper(BaseWebScraper):
    """智谱AI爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://www.zhipuai.cn",
            company_name="zhipu"
        )
        self.news_url = "https://www.zhipuai.cn/news"
    
    async def get_article_list(self, page: int = 1, article_type: str = 'news') -> List[Dict]:
        """获取文章列表"""
        try:
            url = self.news_url
            logger.info(f"Fetching Zhipu AI {article_type} list from {url}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            article_elements = soup.find_all(['article', 'div', 'li'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['news', 'item', 'card']))
            
            if not article_elements:
                article_elements = soup.select('a[href*="/news/"], a[href*="/article/"]')
            
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
                    
                    articles.append({
                        'article_id': f"zhipu_{article_id}",
                        'title': title[:500],
                        'url': url,
                        'article_type': 'news',
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} Zhipu articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Zhipu article list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"Fetching Zhipu article details: {article_id}")
            
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
            content_elem = soup.find(['article', 'div'], class_=lambda x: x and ('content' in str(x).lower() or 'article' in str(x).lower()))
            if not content_elem:
                content_elem = soup.find('main')
            
            article['content'] = self.clean_text(content_elem.get_text()) if content_elem else ''
            
            # 提取参考链接
            reference_links = self.extract_reference_links(soup, content_elem)
            article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
            
            # 描述
            desc_elem = soup.find('meta', attrs={'name': 'description'})
            if desc_elem:
                article['description'] = desc_elem.get('content', '')
            else:
                article['description'] = article['content'][:300]
            
            # 作者
            article['author'] = '智谱AI'
            
            # 发布时间
            time_elem = soup.find(['time', 'span'], class_=lambda x: x and 'time' in str(x).lower())
            time_str = time_elem.get_text() if time_elem else ''
            
            article['publish_time'] = self.parse_timestamp(time_str) if time_str else utils.get_current_timestamp()
            article['publish_date'] = datetime.fromtimestamp(article['publish_time']).strftime('%Y-%m-%d')
            
            # 分类和标签
            article['category'] = 'AI News'
            article['tags'] = ''
            article['cover_image'] = ''
            article['article_type'] = 'news'
            article['is_research'] = 0
            article['is_product'] = 1 if any(keyword in article['title'] for keyword in ['GLM', '智谱', '发布', '产品']) else 0
            
            return article
        
        except Exception as e:
            logger.error(f"Failed to get Zhipu article details {article_id}: {e}")
            return None


class AlibabaQwenScraper(BaseWebScraper):
    """阿里云通义千问爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://tongyi.aliyun.com",
            company_name="alibaba"
        )
        self.blog_url = "https://developer.aliyun.com/topic/tongyi"  # 更新为专题页
    
    async def get_article_list(self, page: int = 1, article_type: str = 'blog') -> List[Dict]:
        """获取文章列表"""
        try:
            # 默认爬取博客，因为官网首页通常是动态加载的
            url = self.blog_url if article_type == 'blog' else self.base_url
            logger.info(f"Fetching Alibaba Qwen {article_type} list from {url}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            article_elements = soup.find_all(['article', 'div', 'li'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['news', 'item', 'list', 'card', 'article']))
            
            if not article_elements:
                article_elements = soup.select('a[href*="/article/"], a[href*="/news/"]')
            
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
                        url = 'https://developer.aliyun.com' + url if 'developer' in self.blog_url else self.base_url + url
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
                        'article_id': f"alibaba_{article_id}",
                        'title': title[:500],
                        'url': url,
                        'article_type': 'blog' if 'developer' in url else 'news',
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} Alibaba Qwen articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Alibaba Qwen article list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"Fetching Alibaba Qwen article details: {article_id}")
            
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
            content_elem = soup.find(['article', 'div'], class_=lambda x: x and ('content' in str(x).lower() or 'article' in str(x).lower()))
            if not content_elem:
                content_elem = soup.find('main')
            
            article['content'] = self.clean_text(content_elem.get_text()) if content_elem else ''
            
            # 提取参考链接
            reference_links = self.extract_reference_links(soup, content_elem)
            article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
            
            # 描述
            desc_elem = soup.find('meta', attrs={'name': 'description'})
            if desc_elem:
                article['description'] = desc_elem.get('content', '')
            else:
                article['description'] = article['content'][:300]
            
            # 作者
            article['author'] = '阿里云通义'
            
            # 发布时间
            time_elem = soup.find(['time', 'span'], class_=lambda x: x and 'time' in str(x).lower())
            time_str = time_elem.get_text() if time_elem else ''
            
            article['publish_time'] = self.parse_timestamp(time_str) if time_str else utils.get_current_timestamp()
            article['publish_date'] = datetime.fromtimestamp(article['publish_time']).strftime('%Y-%m-%d')
            
            # 分类和标签
            article['category'] = 'AI News'
            article['tags'] = ''
            article['cover_image'] = ''
            article['article_type'] = 'blog' if 'developer' in url else 'news'
            article['is_research'] = 0
            article['is_product'] = 1 if any(keyword in article['title'] for keyword in ['通义', 'Qwen', '发布', '产品']) else 0
            
            return article
        
        except Exception as e:
            logger.error(f"Failed to get Alibaba Qwen article details {article_id}: {e}")
            return None


class MoonshotAIScraper(BaseWebScraper):
    """Moonshot AI（月之暗面）爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://www.moonshot.cn",
            company_name="moonshot"
        )
    
    async def get_article_list(self, page: int = 1, article_type: str = 'news') -> List[Dict]:
        """获取文章列表"""
        try:
            url = self.base_url
            logger.info(f"Fetching Moonshot AI {article_type} list from {url}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            article_elements = soup.find_all(['article', 'div', 'li'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['news', 'item', 'card']))
            
            if not article_elements:
                article_elements = soup.select('a[href*="/news/"], a[href*="/article/"]')
            
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
                    
                    articles.append({
                        'article_id': f"moonshot_{article_id}",
                        'title': title[:500],
                        'url': url,
                        'article_type': 'news',
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} Moonshot AI articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Moonshot AI article list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"Fetching Moonshot AI article details: {article_id}")
            
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
            content_elem = soup.find(['article', 'div'], class_=lambda x: x and ('content' in str(x).lower() or 'article' in str(x).lower()))
            if not content_elem:
                content_elem = soup.find('main')
            
            article['content'] = self.clean_text(content_elem.get_text()) if content_elem else ''
            
            # 提取参考链接
            reference_links = self.extract_reference_links(soup, content_elem)
            article['reference_links'] = json.dumps(reference_links, ensure_ascii=False) if reference_links else ''
            
            # 描述
            desc_elem = soup.find('meta', attrs={'name': 'description'})
            if desc_elem:
                article['description'] = desc_elem.get('content', '')
            else:
                article['description'] = article['content'][:300]
            
            # 作者
            article['author'] = 'Moonshot AI'
            
            # 发布时间
            time_elem = soup.find(['time', 'span'], class_=lambda x: x and 'time' in str(x).lower())
            time_str = time_elem.get_text() if time_elem else ''
            
            article['publish_time'] = self.parse_timestamp(time_str) if time_str else utils.get_current_timestamp()
            article['publish_date'] = datetime.fromtimestamp(article['publish_time']).strftime('%Y-%m-%d')
            
            # 分类和标签
            article['category'] = 'AI News'
            article['tags'] = ''
            article['cover_image'] = ''
            article['article_type'] = 'news'
            article['is_research'] = 0
            article['is_product'] = 1 if any(keyword in article['title'] for keyword in ['Kimi', '发布', '产品']) else 0
            
            return article
        
        except Exception as e:
            logger.error(f"Failed to get Moonshot AI article details {article_id}: {e}")
            return None


async def run_china_ai_crawler(days: int = 7):
    """运行国内AI公司爬虫"""
    logger.info("=" * 60)
    logger.info("🚀 China AI Companies Crawler Started")
    logger.info("=" * 60)
    
    # 智谱AI
    zhipu_scraper = ZhipuAIScraper()
    await zhipu_scraper.init()
    
    try:
        logger.info("Fetching Zhipu AI articles...")
        articles = await zhipu_scraper.get_article_list()
        
        for article_item in articles[:15]:
            try:
                article = await zhipu_scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing Zhipu article: {e}")
                continue
    finally:
        await zhipu_scraper.close()
    
    # 阿里云通义
    alibaba_scraper = AlibabaQwenScraper()
    await alibaba_scraper.init()
    
    try:
        logger.info("Fetching Alibaba Qwen articles...")
        articles = await alibaba_scraper.get_article_list()
        
        for article_item in articles[:15]:
            try:
                article = await alibaba_scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing Alibaba article: {e}")
                continue
    finally:
        await alibaba_scraper.close()
    
    # Moonshot AI
    moonshot_scraper = MoonshotAIScraper()
    await moonshot_scraper.init()
    
    try:
        logger.info("Fetching Moonshot AI articles...")
        articles = await moonshot_scraper.get_article_list()
        
        for article_item in articles[:15]:
            try:
                article = await moonshot_scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing Moonshot article: {e}")
                continue
    finally:
        await moonshot_scraper.close()
        logger.info("China AI Companies Crawler finished.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_china_ai_crawler())

