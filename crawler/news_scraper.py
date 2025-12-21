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
from database.models import JiqizhixinArticle
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
    
    async def get_article_list(self, target_date: Optional[str] = None) -> List[Dict]:
        """
        获取指定日期的文章列表
        
        Args:
            target_date: 目标日期，格式为 YYYY-MM-DD，如果为None则使用今天
            
        Returns:
            文章列表
        """
        try:
            if target_date is None:
                target_date = datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"Fetching Jiqizhixin articles for date: {target_date}")
            
            articles = []
            max_articles = 20  # 最多20篇文章
            
            # 第一篇：直接使用日期，不带序号
            base_url_pattern = f"{self.base_url}/articles/{target_date}"
            
            # 尝试第一篇（不带序号）
            url = base_url_pattern
            article_id = f"jiqizhixin_{target_date}"
            
            # 测试URL是否可访问
            html = await self.fetch_page(url)
            if html:
                articles.append({
                    'article_id': article_id,
                    'url': url,
                    'publish_date': target_date
                })
                logger.info(f"Found article: {url}")
            else:
                logger.warning(f"First article not found for {target_date}")
                return []  # 如果第一篇都访问失败，说明该日期没有文章
            
            # 从第二篇开始，使用序号（2-20）
            for article_num in range(2, max_articles + 1):
                url = f"{base_url_pattern}-{article_num}"
                article_id = f"jiqizhixin_{target_date}-{article_num}"
                
                # 测试URL是否可访问
                html = await self.fetch_page(url)
                if html:
                    articles.append({
                        'article_id': article_id,
                        'url': url,
                        'publish_date': target_date
                    })
                    logger.info(f"Found article {article_num}: {url}")
                else:
                    # 访问失败，说明该日期的文章已经爬取完毕
                    logger.info(f"Article {article_num} not found, stopping crawl for {target_date}")
                    break
                
                # 添加延迟避免请求过快
                await asyncio.sleep(1)
            
            logger.info(f"Found {len(articles)} articles for date {target_date}")
            return articles
        
        except Exception as e:
            logger.error(f"Failed to get Jiqizhixin article list for {target_date}: {e}")
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
            
            # 标题 - 尝试多种方式提取
            article['title'] = ''
            
            # 1. 优先查找 h1 标签
            title_elem = soup.find('h1')
            if title_elem:
                article['title'] = self.clean_text(title_elem.get_text())
            
            # 2. 如果h1没找到，查找包含 title 类的元素
            if not article['title']:
                title_elem = soup.find(['h1', 'h2', 'div'], class_=lambda x: x and 'title' in str(x).lower())
                if title_elem:
                    article['title'] = self.clean_text(title_elem.get_text())
            
            # 3. 查找 og:title meta 标签
            if not article['title']:
                og_title = soup.find('meta', attrs={'property': 'og:title'})
                if og_title and og_title.get('content'):
                    article['title'] = og_title.get('content').strip()
            
            # 4. 从 title 标签提取
            if not article['title']:
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    # 移除网站名称（如" | 机器之心"）
                    article['title'] = title_text.split('|')[0].split('-')[0].strip()
            
            # 5. 确保标题不为空
            if not article['title']:
                article['title'] = f"机器之心文章 {article_id}"
                logger.warning(f"无法提取标题，使用默认标题: {article['title']}")
            else:
                logger.info(f"提取到标题: {article['title'][:50]}...")
            
            # 内容 - 尝试多种选择器
            content_elem = None
            
            # 1. 尝试查找 article 标签
            content_elem = soup.find('article')
            
            # 2. 尝试查找包含 content/article/post/detail/body 类的 div
            if not content_elem:
                for class_keyword in ['content', 'article', 'post', 'detail', 'body', 'text', 'main-content']:
                    content_elem = soup.find('div', class_=lambda x: x and class_keyword in str(x).lower())
                    if content_elem:
                        # 检查内容长度，确保不是导航栏等
                        text = content_elem.get_text(strip=True)
                        if len(text) > 100:  # 至少100字符才认为是正文
                            break
                        else:
                            content_elem = None
            
            # 3. 尝试查找 main 标签
            if not content_elem:
                main_elem = soup.find('main')
                if main_elem:
                    text = main_elem.get_text(strip=True)
                    if len(text) > 100:
                        content_elem = main_elem
            
            # 4. 尝试查找包含文章内容的特定ID或class
            if not content_elem:
                # 尝试查找常见的文章容器ID
                for id_name in ['article-content', 'post-content', 'content', 'article-body', 'main-content']:
                    content_elem = soup.find(id=id_name)
                    if content_elem:
                        break
            
            # 5. 如果还是没找到，尝试查找所有div，选择文本最长的
            if not content_elem:
                all_divs = soup.find_all('div', class_=True)
                max_length = 0
                best_div = None
                for div in all_divs:
                    text = div.get_text(strip=True)
                    # 排除导航、侧边栏等
                    classes = ' '.join(div.get('class', [])).lower()
                    if any(exclude in classes for exclude in ['nav', 'menu', 'sidebar', 'footer', 'header', 'ad', 'comment']):
                        continue
                    if len(text) > max_length and len(text) > 200:  # 至少200字符
                        max_length = len(text)
                        best_div = div
                if best_div:
                    content_elem = best_div
            
            # 提取内容
            if content_elem:
                # 移除不需要的元素（导航、广告、评论等）
                for unwanted in content_elem.find_all(['nav', 'aside', 'header', 'footer', 'script', 'style']):
                    unwanted.decompose()
                
                # 移除包含特定类的元素
                for unwanted_class in ['nav', 'menu', 'sidebar', 'ad', 'advertisement', 'comment', 'related', 'share']:
                    for elem in content_elem.find_all(class_=lambda x: x and unwanted_class in str(x).lower()):
                        elem.decompose()
                
                article['content'] = self.clean_text(content_elem.get_text())
            else:
                article['content'] = ''
                logger.warning(f"无法提取内容，article_id: {article_id}")
            
            # 如果内容为空或太短，尝试从meta description获取
            if not article['content'] or len(article['content']) < 50:
                desc_elem = soup.find('meta', attrs={'property': 'og:description'})
                if desc_elem and desc_elem.get('content'):
                    article['content'] = desc_elem.get('content')
                    logger.info(f"使用 og:description 作为内容，article_id: {article_id}")
            
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
            
            # 发布时间提取逻辑增强（参考GoogleAIScraper）
            time_str = None
            
            # 1. 尝试从JSON-LD提取
            ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in ld_scripts:
                try:
                    if not script.string:
                        continue
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    
                    # 递归查找 datePublished
                    def find_date(obj):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if k in ['datePublished', 'dateCreated', 'dateModified']:
                                    return v
                                if isinstance(v, (dict, list)):
                                    res = find_date(v)
                                    if res: return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_date(item)
                                if res: return res
                        return None
                    
                    time_str = find_date(data)
                    if time_str:
                        logger.debug(f"Found date in JSON-LD: {time_str}")
                        break
                except Exception:
                    continue
            
            # 2. 尝试从meta标签提取
            if not time_str:
                time_elem = soup.find('meta', attrs={'property': 'article:published_time'})
                if time_elem:
                    time_str = time_elem.get('content', '')
                if not time_str:
                    time_elem = soup.find('meta', attrs={'name': 'publishdate'})
                    if time_elem:
                        time_str = time_elem.get('content', '')
                if not time_str:
                    time_elem = soup.find('meta', attrs={'name': 'date'})
                    if time_elem:
                        time_str = time_elem.get('content', '')
            
            # 3. 尝试从time标签提取
            if not time_str:
                time_elem = soup.find('time')
                if time_elem:
                    time_str = time_elem.get('datetime') or time_elem.get_text(strip=True)
            
            # 4. 尝试从class包含time/date的span/div提取
            if not time_str:
                time_elem = soup.find(['span', 'div'], class_=lambda x: x and ('time' in str(x).lower() or 'date' in str(x).lower() or 'publish' in str(x).lower()))
                if time_elem:
                    time_str = time_elem.get_text(strip=True)
            
            # 5. 如果仍然没有找到，尝试从URL或文章ID中提取日期（作为fallback）
            if not time_str:
                # 尝试从URL中提取日期模式 YYYY-MM-DD
                # URL格式: https://www.jiqizhixin.com/articles/2025-12-21 或 /articles/2025-12-21-3
                url_match = re.search(r'/articles/(\d{4}-\d{2}-\d{2})(?:-\d+)?', url)
                if url_match:
                    date_str = url_match.group(1)
                    time_str = f"{date_str} 12:00:00"  # 默认设置为中午12点
                    logger.debug(f"Extracted date from URL: {date_str}")
            
            # 6. 如果仍然没有找到，尝试从article_id中提取日期
            if not time_str:
                # article_id格式: jiqizhixin_2025-12-21 或 jiqizhixin_2025-12-21-3
                id_match = re.search(r'jiqizhixin_(\d{4}-\d{2}-\d{2})', article_id)
                if id_match:
                    date_str = id_match.group(1)
                    time_str = f"{date_str} 12:00:00"
                    logger.debug(f"Extracted date from article_id: {date_str}")
            
            if not time_str:
                logger.warning(f"Skip article {article_id}: missing publish time.")
                return None
            
            publish_ts = self.parse_timestamp(time_str)
            if publish_ts is None:
                logger.warning(f"Skip article {article_id}: cannot parse publish time: {time_str}")
                return None
            article['publish_time'] = publish_ts
            article['publish_date'] = datetime.fromtimestamp(publish_ts).strftime('%Y-%m-%d')
            
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
    """保存新闻文章到数据库（使用JiqizhixinArticle表）"""
    async with get_session() as session:
        article_id = article.get('article_id')
        
        stmt = select(JiqizhixinArticle).where(JiqizhixinArticle.article_id == article_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.last_modify_ts = utils.get_current_timestamp()
            for key, value in article.items():
                if hasattr(existing, key) and key not in ['id', 'add_ts']:
                    setattr(existing, key, value)
            logger.info(f"Updated Jiqizhixin article: {article_id}")
        else:
            article['add_ts'] = utils.get_current_timestamp()
            article['last_modify_ts'] = utils.get_current_timestamp()
            article['source_keyword'] = 'jiqizhixin'  # 标记来源
            
            valid_keys = {c.name for c in JiqizhixinArticle.__table__.columns}
            filtered_article = {k: v for k, v in article.items() if k in valid_keys}
            
            db_article = JiqizhixinArticle(**filtered_article)
            session.add(db_article)
            logger.info(f"Saved new Jiqizhixin article: {article_id}")


async def run_jiqizhixin_crawler(days: int = 7):
    """运行机器之心爬虫"""
    logger.info("=" * 60)
    logger.info("🚀 Jiqizhixin Crawler Started")
    logger.info("=" * 60)
    
    start_date = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    
    scraper = JiqizhixinScraper()
    await scraper.init()
    
    try:
        # 遍历日期范围内的每一天
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            logger.info(f"Processing date: {date_str}")
            
            # 获取该日期的所有文章
            articles = await scraper.get_article_list(target_date=date_str)
            
            if not articles:
                logger.info(f"No articles found for {date_str}")
            else:
                for article_item in articles:
                    try:
                        article = await scraper.get_article_detail(
                            article_item['article_id'],
                            article_item['url']
                        )
                        
                        if not article:
                            continue
                        
                        await save_news_article_to_db(article)
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Error processing Jiqizhixin article {article_item['article_id']}: {e}")
                        continue
            
            # 移动到下一天
            current_date += timedelta(days=1)
            await asyncio.sleep(2)  # 日期之间的延迟
        
    finally:
        await scraper.close()
        logger.info("Jiqizhixin Crawler finished.")


if __name__ == "__main__":
    asyncio.run(run_jiqizhixin_crawler())
