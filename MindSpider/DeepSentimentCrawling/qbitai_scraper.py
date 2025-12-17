#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量子位(QbitAI)网站爬虫 - 直接爬取脚本
无需登陆，直接爬取近两周的文章到数据库
"""

import asyncio
import json
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    # 1. 先导入 MindSpider 的配置
    import config as mindspider_config
    settings = mindspider_config.settings
    
    # 2. 关键步骤：从 sys.modules 中移除 config
    # 这样后续 MediaCrawler 导入 config 时，会重新加载为 MediaCrawler/config 包
    # 而不是复用 MindSpider/config.py 模块
    if 'config' in sys.modules:
        del sys.modules['config']
        
    from loguru import logger
    import httpx
    from bs4 import BeautifulSoup
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
except ImportError as e:
    print(f"缺少依赖包: {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)

# 导入数据库模型
# 使用 insert(0) 确保优先从 MediaCrawler 目录查找 config 包
media_crawler_path = project_root / "DeepSentimentCrawling/MediaCrawler"
sys.path.insert(0, str(media_crawler_path))

from database.models import QbitaiArticle, QbitaiArticleComment, Base
from database.db_session import get_session
from tools import utils


class QbitaiWebScraper:
    """量子位网站直接爬虫"""
    
    def __init__(self):
        self.base_url = "https://www.qbitai.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        self.session = None
    
    async def init(self):
        """初始化HTTP客户端"""
        self.session = httpx.AsyncClient(headers=self.headers, timeout=30)
    
    async def close(self):
        """关闭HTTP客户端"""
        if self.session:
            await self.session.aclose()
    
    async def fetch_page(self, url: str, **kwargs) -> Optional[str]:
        """获取页面内容"""
        try:
            response = await self.session.get(url, **kwargs)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取页面失败 {url}: {e}")
            return None
    
    async def get_article_list(self, page: int = 1) -> List[Dict]:
        """获取文章列表"""
        try:
            logger.info(f"获取第 {page} 页文章列表...")
            
            # 量子位主页或列表页
            if page == 1:
                url = f"{self.base_url}/"
            else:
                url = f"{self.base_url}/?page={page}"
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # 查找文章元素 - 针对量子位官网结构优化
            # 主要结构是 div.picture_text
            article_elements = soup.find_all('div', class_='picture_text')
            
            if not article_elements:
                # 备用选择器
                article_elements = soup.find_all(class_=re.compile(r'article|news|post|item', re.I))
            
            if not article_elements:
                # 最后尝试查找所有链接
                article_elements = soup.select('a[href*="/article"], a[href*="/news"]')
            
            logger.info(f"找到 {len(article_elements)} 个可能的文章元素")
            
            for elem in article_elements[:20]:  # 限制每页20篇
                try:
                    # 提取标题和链接
                    # 针对 picture_text 结构
                    if 'picture_text' in elem.get('class', []):
                        title_elem = elem.select_one('.text_box h4 a')
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            url = title_elem.get('href', '')
                        else:
                            continue
                    elif elem.name == 'a':
                        title = elem.get_text(strip=True)
                        url = elem.get('href', '')
                    else:
                        title_elem = elem.find(['h2', 'h3', 'h4', 'a'])
                        title = title_elem.get_text(strip=True) if title_elem else ''
                        
                        link_elem = elem.find('a', href=re.compile(r'article|news'))
                        url = link_elem.get('href', '') if link_elem else ''
                    
                    if not url or not title:
                        continue
                    
                    # 规范化URL
                    if not url.startswith('http'):
                        url = urljoin(self.base_url, url)
                    
                    # 提取文章ID
                    article_id = self._extract_article_id(url)
                    if not article_id:
                        continue
                    
                    articles.append({
                        'article_id': article_id,
                        'title': title[:500],
                        'url': url,
                    })
                    logger.debug(f"提取文章: {article_id} - {title[:30]}")
                    
                except Exception as e:
                    logger.warning(f"处理文章元素失败: {e}")
                    continue
            
            logger.info(f"第 {page} 页共获取 {len(articles)} 篇文章")
            return articles
        
        except Exception as e:
            logger.error(f"获取文章列表失败: {e}")
            return []
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            logger.info(f"获取文章详情: {article_id}")
            
            html = await self.fetch_page(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            article = {
                'article_id': article_id,
                'url': url,
            }
            
            # 标题
            title_elem = soup.find(['h1', 'h2'], class_=re.compile(r'title', re.I))
            article['title'] = title_elem.get_text(strip=True) if title_elem else ''
            
            # 内容
            content_elem = soup.find(class_=re.compile(r'content|article-body|main', re.I))
            article['content'] = content_elem.get_text(strip=True) if content_elem else ''
            
            # 描述/摘要
            desc_elem = soup.find(class_=re.compile(r'desc|summary|intro', re.I))
            article['description'] = desc_elem.get_text(strip=True) if desc_elem else article['content'][:200]
            
            # 作者
            author_elem = soup.find(class_=re.compile(r'author', re.I))
            article['author'] = author_elem.get_text(strip=True) if author_elem else ''
            
            # 发布时间
            time_elem = soup.find(['time', 'span'], class_=re.compile(r'time|date|pub', re.I))
            if not time_elem:
                time_elem = soup.find('meta', attrs={'property': 'article:published_time'})
                time_str = time_elem.get('content') if time_elem else datetime.now().isoformat()
            else:
                time_str = time_elem.get_text(strip=True) if time_elem.name != 'meta' else time_elem.get('content')
            
            article['publish_time'] = self._parse_timestamp(time_str)
            article['publish_date'] = datetime.fromtimestamp(article['publish_time']).strftime('%Y-%m-%d')
            
            # 分类
            cat_elem = soup.find(class_=re.compile(r'category|cat', re.I))
            article['category'] = cat_elem.get_text(strip=True) if cat_elem else ''
            
            # 标签
            tags = []
            for tag_elem in soup.find_all(class_=re.compile(r'tag', re.I)):
                tag_text = tag_elem.get_text(strip=True)
                if tag_text:
                    tags.append(tag_text)
            article['tags'] = json.dumps(tags, ensure_ascii=False) if tags else ''
            
            # 封面图片
            img_elem = soup.find('img', class_=re.compile(r'cover|featured', re.I))
            article['cover_image'] = img_elem.get('src') if img_elem else ''
            
            # 点赞、评论等数据
            article['read_count'] = 0
            article['like_count'] = 0
            article['comment_count'] = 0
            article['share_count'] = 0
            article['collect_count'] = 0
            article['is_original'] = 1
            
            logger.info(f"成功获取文章详情: {article['title'][:50]}")
            return article
        
        except Exception as e:
            logger.error(f"获取文章详情失败 {article_id}: {e}")
            return None
    
    async def get_comments(self, article_id: str, url: str) -> List[Dict]:
        """获取文章评论"""
        try:
            logger.info(f"获取文章评论: {article_id}")
            
            html = await self.fetch_page(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            comments = []
            
            # 查找评论元素
            comment_elements = soup.find_all(class_=re.compile(r'comment', re.I))
            logger.info(f"找到 {len(comment_elements)} 条评论")
            
            for idx, elem in enumerate(comment_elements[:50]):  # 限制50条评论
                try:
                    # 用户名
                    user_elem = elem.find(class_=re.compile(r'user|author', re.I))
                    user_name = user_elem.get_text(strip=True) if user_elem else f'用户{idx}'
                    
                    # 评论内容
                    content_elem = elem.find(class_=re.compile(r'content|text', re.I))
                    if not content_elem:
                        content_elem = elem.find('p')
                    content = content_elem.get_text(strip=True) if content_elem else ''
                    
                    if not content:
                        continue
                    
                    # 头像
                    avatar_elem = elem.find('img', class_=re.compile(r'avatar', re.I))
                    user_avatar = avatar_elem.get('src') if avatar_elem else ''
                    
                    # 时间
                    time_elem = elem.find(class_=re.compile(r'time|date', re.I))
                    time_str = time_elem.get_text(strip=True) if time_elem else datetime.now().isoformat()
                    publish_time = self._parse_timestamp(time_str)
                    
                    # 点赞数
                    like_elem = elem.find(class_=re.compile(r'like', re.I))
                    like_count = 0
                    if like_elem:
                        match = re.search(r'\d+', like_elem.get_text())
                        like_count = int(match.group()) if match else 0
                    
                    comment = {
                        'comment_id': f"{article_id}_comment_{idx}",
                        'article_id': article_id,
                        'user_name': user_name,
                        'user_avatar': user_avatar,
                        'content': content,
                        'publish_time': publish_time,
                        'publish_date': datetime.fromtimestamp(publish_time).strftime('%Y-%m-%d'),
                        'like_count': like_count,
                        'sub_comment_count': 0,
                        'parent_comment_id': None,
                    }
                    comments.append(comment)
                    
                except Exception as e:
                    logger.warning(f"处理评论失败: {e}")
                    continue
            
            logger.info(f"成功提取 {len(comments)} 条评论")
            return comments
        
        except Exception as e:
            logger.error(f"获取评论失败 {article_id}: {e}")
            return []
    
    def _extract_article_id(self, url: str) -> Optional[str]:
        """从URL提取文章ID"""
        patterns = [
            r'/article/(\d+)',
            r'/news/(\d+)',
            r'/(\d+)\.html',
            r'/article/([^/]+)',
            r'article[=/]([^&/?]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # 最后使用URL的hash
        return url.split('/')[-1].split('.')[0] if url else None
    
    def _parse_timestamp(self, time_str: str) -> int:
        """解析时间字符串为时间戳"""
        try:
            if not time_str:
                return int(datetime.now().timestamp())
            
            time_str = time_str.strip()
            now = datetime.now()
            
            # 处理相对时间
            if '刚刚' in time_str:
                return int(now.timestamp())
            elif '分钟前' in time_str:
                minutes = int(re.search(r'(\d+)', time_str).group(1))
                return int((now - timedelta(minutes=minutes)).timestamp())
            elif '小时前' in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                return int((now - timedelta(hours=hours)).timestamp())
            elif '天前' in time_str:
                days = int(re.search(r'(\d+)', time_str).group(1))
                return int((now - timedelta(days=days)).timestamp())
            elif '昨天' in time_str:
                # 昨天 15:28
                time_part = re.search(r'(\d{1,2}:\d{1,2})', time_str)
                if time_part:
                    dt_str = f"{(now - timedelta(days=1)).strftime('%Y-%m-%d')} {time_part.group(1)}"
                    return int(datetime.strptime(dt_str, '%Y-%m-%d %H:%M').timestamp())
                else:
                    return int((now - timedelta(days=1)).timestamp())
            elif '前天' in time_str:
                return int((now - timedelta(days=2)).timestamp())
            
            # 尝试多种格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y/%m/%d %H:%M:%S',
                '%Y年%m月%d日 %H:%M:%S',
                '%Y年%m月%d日',
                '%Y-%m-%d',
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(time_str[:19], fmt)
                    return int(dt.timestamp())
                except:
                    pass
            
            return int(datetime.now().timestamp())
        except:
            return int(datetime.now().timestamp())


async def save_article_to_db(article: Dict):
    """保存文章到数据库"""
    try:
        async with get_session() as session:
            article_id = article.get('article_id')
            
            if 'url' in article:
                article['article_url'] = article.pop('url')
            
            # 检查是否已存在
            stmt = select(QbitaiArticle).where(QbitaiArticle.article_id == article_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"文章已存在，更新: {article_id}")
                existing.last_modify_ts = utils.get_current_timestamp()
                for key, value in article.items():
                    if hasattr(existing, key) and key not in ['id', 'add_ts']:
                        setattr(existing, key, value)
            else:
                logger.info(f"保存新文章: {article_id}")
                article['add_ts'] = utils.get_current_timestamp()
                article['last_modify_ts'] = utils.get_current_timestamp()
                
                # 过滤掉不在模型中的字段
                valid_keys = {c.name for c in QbitaiArticle.__table__.columns}
                filtered_article = {k: v for k, v in article.items() if k in valid_keys}
                
                db_article = QbitaiArticle(**filtered_article)
                session.add(db_article)
            
            await session.commit()
            logger.info(f"文章保存成功: {article_id}")
    except Exception as e:
        logger.error(f"保存文章失败: {e}")
        raise


async def save_comment_to_db(comment: Dict):
    """保存评论到数据库"""
    try:
        async with get_session() as session:
            comment_id = comment.get('comment_id')
            
            # 检查是否已存在
            stmt = select(QbitaiArticleComment).where(QbitaiArticleComment.comment_id == comment_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"评论已存在，更新: {comment_id}")
                existing.last_modify_ts = utils.get_current_timestamp()
                for key, value in comment.items():
                    if hasattr(existing, key) and key not in ['id', 'add_ts']:
                        setattr(existing, key, value)
            else:
                logger.info(f"保存新评论: {comment_id}")
                comment['add_ts'] = utils.get_current_timestamp()
                comment['last_modify_ts'] = utils.get_current_timestamp()
                
                # 过滤掉不在模型中的字段
                valid_keys = {c.name for c in QbitaiArticleComment.__table__.columns}
                filtered_comment = {k: v for k, v in comment.items() if k in valid_keys}
                
                db_comment = QbitaiArticleComment(**filtered_comment)
                session.add(db_comment)
            
            await session.commit()
            logger.info(f"评论保存成功: {comment_id}")
    except Exception as e:
        logger.error(f"保存评论失败: {e}")


async def main():
    """主爬取流程"""
    logger.info("=" * 60)
    logger.info("🚀 量子位(QbitAI)爬虫启动")
    logger.info(f"📍 网址: https://www.qbitai.com/")
    logger.info(f"📅 爬取周期: 近两周内容")
    logger.info("=" * 60)
    
    # 计算时间范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    logger.info(f"⏰ 时间范围: {start_date.date()} 到 {end_date.date()}")
    
    scraper = QbitaiWebScraper()
    await scraper.init()
    
    try:
        total_articles = 0
        total_comments = 0
        page = 1
        
        while True:
            # 获取文章列表
            articles = await scraper.get_article_list(page=page)
            
            if not articles:
                logger.info("已到达最后一页或没有更多文章")
                break
            
            for article_item in articles:
                try:
                    # 获取完整文章详情
                    article = await scraper.get_article_detail(
                        article_item['article_id'],
                        article_item['url']
                    )
                    
                    if article:
                        # 检查是否在时间范围内
                        article_date = article.get('publish_date')
                        if article_date < str(start_date.date()):
                            logger.info(f"文章日期 {article_date} 已超出时间范围，停止爬取")
                            await scraper.close()
                            return total_articles, total_comments
                        
                        # 保存文章到数据库
                        await save_article_to_db(article)
                        total_articles += 1
                        
                        # 获取评论
                        try:
                            comments = await scraper.get_comments(
                                article_item['article_id'],
                                article_item['url']
                            )
                            
                            for comment in comments:
                                try:
                                    await save_comment_to_db(comment)
                                    total_comments += 1
                                except Exception as e:
                                    logger.warning(f"保存评论失败: {e}")
                        except Exception as e:
                            logger.warning(f"获取评论失败: {e}")
                        
                        # 礼貌延迟
                        await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"处理文章失败: {e}")
                    continue
            
            page += 1
            # 列表页延迟
            await asyncio.sleep(2)
        
        return total_articles, total_comments
    
    finally:
        await scraper.close()


if __name__ == "__main__":
    try:
        articles, comments = asyncio.run(main())
        logger.info("=" * 60)
        logger.info(f"✅ 爬取完成!")
        logger.info(f"📊 统计结果:")
        logger.info(f"   - 文章总数: {articles}")
        logger.info(f"   - 评论总数: {comments}")
        logger.info(f"💾 数据已保存到数据库")
        logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.warning("用户中断爬取")
        sys.exit(0)
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        sys.exit(1)
