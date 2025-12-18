#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anthropic Research & News Scraper
爬取Anthropic官网的研究论文和新闻
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from crawler.base_scraper import BaseWebScraper
from crawler.openai_scraper import save_company_article_to_db
from crawler import utils

logger = utils.setup_logger()


class AnthropicScraper(BaseWebScraper):
    """Anthropic官网爬虫"""
    
    def __init__(self):
        super().__init__(
            base_url="https://www.anthropic.com",
            company_name="anthropic"
        )
        self.news_url = "https://www.anthropic.com/news"
        self.research_url = "https://www.anthropic.com/research"
    
    async def get_article_list(self, page: int = 1, article_type: str = 'news') -> List[Dict]:
        """获取文章列表"""
        try:
            if article_type == 'news':
                url = self.news_url
            elif article_type == 'research':
                url = self.research_url
            else:
                url = self.news_url
            
            logger.info(f"Fetching Anthropic {article_type} list from {url}...")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # Anthropic网站的文章通常在article、div.card等元素中
            article_elements = soup.find_all(['article', 'div'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['post', 'card', 'item', 'article']))
            
            if not article_elements:
                article_elements = soup.select('a[href*="/news/"], a[href*="/research/"]')
            
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
                    elif '/news/' in url:
                        determined_type = 'news'
                    else:
                        determined_type = article_type
                    
                    articles.append({
                        'article_id': f"anthropic_{article_id}",
                        'title': title[:500],
                        'url': url,
                        'article_type': determined_type,
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue
            
            logger.info(f"Extracted {len(articles)} Anthropic articles")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Anthropic article list: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"Fetching Anthropic article details: {article_id}")
            
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
                article['author'] = author_elem.get('content', '') if author_elem else 'Anthropic'
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
            article['category'] = 'AI Research' if '/research/' in url else 'AI News'
            
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
            article['article_type'] = 'research' if '/research/' in url else 'news'
            article['is_research'] = 1 if article['article_type'] == 'research' else 0
            article['is_product'] = 1 if any(keyword in article['title'].lower() for keyword in ['claude', 'api', 'product', 'launch', 'release', 'announce']) else 0
            
            return article
        
        except Exception as e:
            logger.error(f"Failed to get Anthropic article details {article_id}: {e}")
            return None


async def run_anthropic_crawler(days: int = 7):
    """运行Anthropic爬虫"""
    logger.info("=" * 60)
    logger.info("🚀 Anthropic Crawler Started")
    logger.info("=" * 60)
    
    scraper = AnthropicScraper()
    await scraper.init()
    
    try:
        # 爬取新闻文章
        logger.info("Fetching Anthropic news articles...")
        news_articles = await scraper.get_article_list(article_type='news')
        
        for article_item in news_articles[:20]:
            try:
                article = await scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing Anthropic news article: {e}")
                continue
        
        # 爬取研究文章
        logger.info("Fetching Anthropic research articles...")
        research_articles = await scraper.get_article_list(article_type='research')
        
        for article_item in research_articles[:20]:
            try:
                article = await scraper.get_article_detail(
                    article_item['article_id'],
                    article_item['url']
                )
                
                if article:
                    await save_company_article_to_db(article)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing Anthropic research article: {e}")
                continue
        
    finally:
        await scraper.close()
        logger.info("Anthropic Crawler finished.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_anthropic_crawler())

