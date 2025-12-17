# -*- coding: utf-8 -*-
# @Author  : MindSpider
# @Time    : 2025/12/16
# @Desc    : 量子位爬虫客户端 - API请求处理

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from playwright.async_api import Page

from tools import utils


class QbitaiClient:
    """量子位爬虫客户端"""

    def __init__(self, playwright_page: Page, timeout: int = 30):
        self.playwright_page = playwright_page
        self.timeout = timeout
        self._host = "https://www.qbitai.com"
        self.headers = {
            "User-Agent": utils.get_user_agent(),
            "Referer": "https://www.qbitai.com/",
        }

    async def get_article_list(self, page: int = 1) -> List[Dict]:
        """获取文章列表"""
        try:
            url = f"{self._host}/"
            params = {"page": page}
            
            # 使用Playwright获取页面
            goto_url = f"{url}?page={page}" if page > 1 else url
            await self.playwright_page.goto(goto_url, wait_until="domcontentloaded")
            
            # 等待文章列表加载
            await self.playwright_page.wait_for_selector(".news-item, .article-item, article", timeout=10000)
            
            # 提取文章信息
            articles = await self.playwright_page.evaluate("""
                () => {
                    const items = document.querySelectorAll('.news-item, .article-item, article, .article-title');
                    const articles = [];
                    
                    items.forEach(item => {
                        try {
                            // 尝试多种选择器组合来获取标题和链接
                            let titleEl = item.querySelector('h2, h3, h4, .title, .article-title, a[title]');
                            let linkEl = item.querySelector('a[href*="article"], a[href*="news"], a');
                            
                            if (!titleEl && linkEl) {
                                titleEl = linkEl;
                            }
                            
                            if (titleEl && linkEl) {
                                const title = titleEl.textContent?.trim() || titleEl.getAttribute('title') || '';
                                const href = linkEl.getAttribute('href') || '';
                                
                                if (title && href) {
                                    let fullUrl = href;
                                    if (!href.startsWith('http')) {
                                        fullUrl = window.location.origin + (href.startsWith('/') ? '' : '/') + href;
                                    }
                                    
                                    articles.push({
                                        title: title,
                                        url: fullUrl,
                                        href: href
                                    });
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing article:', e);
                        }
                    });
                    
                    return articles;
                }
            """)
            
            utils.logger.info(f"获取到 {len(articles)} 篇文章")
            
            # 处理获取到的文章
            result = []
            for idx, article in enumerate(articles):
                try:
                    article_id = self._extract_article_id(article['url'])
                    if article_id:
                        result.append({
                            'article_id': article_id,
                            'title': article['title'],
                            'url': article['url'],
                            'publish_date': datetime.now().date(),  # 稍后在详情页更新
                        })
                except Exception as e:
                    utils.logger.warning(f"处理文章失败: {e}")
                    continue
            
            return result
        except Exception as e:
            utils.logger.error(f"获取文章列表失败: {e}")
            return []

    async def get_article_detail(self, article_id: str) -> Optional[Dict]:
        """获取文章详情"""
        try:
            # 构造文章URL
            url = f"{self._host}/article/{article_id}"
            
            await self.playwright_page.goto(url, wait_until="domcontentloaded")
            
            # 等待内容加载
            await self.playwright_page.wait_for_timeout(2000)
            
            # 提取详细信息
            article_data = await self.playwright_page.evaluate("""
                () => {
                    const data = {};
                    
                    // 标题
                    const titleEl = document.querySelector('h1, .article-title, .title');
                    data.title = titleEl?.textContent?.trim() || '';
                    
                    // 内容
                    const contentEl = document.querySelector('.article-content, .content, .main-content, article');
                    data.content = contentEl?.innerHTML || '';
                    
                    // 描述/摘要
                    const descEl = document.querySelector('.article-desc, .desc, .summary, .description');
                    data.description = descEl?.textContent?.trim() || '';
                    
                    // 作者
                    const authorEl = document.querySelector('.author, .author-name, [class*="author"]');
                    data.author = authorEl?.textContent?.trim() || '';
                    
                    // 发布时间
                    const timeEl = document.querySelector('.publish-time, .time, .date, time');
                    data.publish_time = timeEl?.textContent?.trim() || timeEl?.getAttribute('datetime') || '';
                    
                    // 分类
                    const categoryEl = document.querySelector('.category, .cat, [class*="category"]');
                    data.category = categoryEl?.textContent?.trim() || '';
                    
                    // 封面图片
                    const imgEl = document.querySelector('img[src*="qbitai"], img.cover, img[class*="cover"]');
                    data.cover_image = imgEl?.getAttribute('src') || '';
                    
                    // 标签
                    const tags = [];
                    document.querySelectorAll('.tag, .tags a, [class*="tag"] a').forEach(el => {
                        tags.push(el.textContent?.trim());
                    });
                    data.tags = tags.filter(t => t);
                    
                    return data;
                }
            """)
            
            article_data['article_id'] = article_id
            article_data['url'] = url
            article_data['publish_date'] = self._parse_publish_date(article_data.get('publish_time', ''))
            article_data['publish_time'] = int(self._parse_publish_timestamp(article_data.get('publish_time', '')))
            
            return article_data
        except Exception as e:
            utils.logger.error(f"获取文章详情失败 {article_id}: {e}")
            return None

    async def get_comments(self, article_id: str) -> List[Dict]:
        """获取文章评论"""
        try:
            # 检查是否有评论区
            comment_section = await self.playwright_page.query_selector(
                '.comments, .comment-section, [class*="comment"]'
            )
            
            if not comment_section:
                utils.logger.info(f"文章 {article_id} 没有评论")
                return []
            
            # 尝试加载所有评论
            try:
                load_more_btn = await self.playwright_page.query_selector(
                    'button:has-text("加载更多"), a:has-text("加载更多"), .load-more'
                )
                if load_more_btn:
                    for _ in range(3):  # 最多点击3次加载更多
                        try:
                            await load_more_btn.click()
                            await asyncio.sleep(1)
                        except:
                            break
            except:
                pass
            
            # 提取评论
            comments = await self.playwright_page.evaluate("""
                () => {
                    const comments = [];
                    document.querySelectorAll('.comment, .comment-item, [class*="comment"]').forEach((item, idx) => {
                        try {
                            const comment = {};
                            
                            // 用户名
                            const userEl = item.querySelector('.user-name, .name, .author');
                            comment.user_name = userEl?.textContent?.trim() || `用户${idx}`;
                            
                            // 评论内容
                            const contentEl = item.querySelector('.comment-content, .content, p');
                            comment.content = contentEl?.textContent?.trim() || '';
                            
                            // 用户头像
                            const avatarEl = item.querySelector('img.avatar, img[class*="avatar"]');
                            comment.user_avatar = avatarEl?.getAttribute('src') || '';
                            
                            // 发布时间
                            const timeEl = item.querySelector('.time, .date, time');
                            comment.publish_time = timeEl?.textContent?.trim() || '';
                            
                            // 点赞数
                            const likeEl = item.querySelector('.like-count, [class*="like"]');
                            comment.like_count = parseInt(likeEl?.textContent || 0);
                            
                            if (comment.content) {
                                comments.push(comment);
                            }
                        } catch (e) {
                            console.error('Error parsing comment:', e);
                        }
                    });
                    
                    return comments;
                }
            """)
            
            # 处理评论数据
            result = []
            for idx, comment in enumerate(comments):
                try:
                    comment['comment_id'] = f"{article_id}_comment_{idx}"
                    comment['article_id'] = article_id
                    comment['publish_time'] = int(self._parse_publish_timestamp(comment.get('publish_time', '')))
                    comment['publish_date'] = datetime.now().date()
                    result.append(comment)
                except Exception as e:
                    utils.logger.warning(f"处理评论失败: {e}")
                    continue
            
            return result
        except Exception as e:
            utils.logger.error(f"获取评论失败 {article_id}: {e}")
            return []

    def _extract_article_id(self, url: str) -> Optional[str]:
        """从URL提取文章ID"""
        # 尝试多种URL格式
        patterns = [
            r'/article/(\d+)',
            r'/news/(\d+)',
            r'/(\d+)\.html',
            r'/article/([^/]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # 如果没有匹配，使用URL的hash
        return url.split('/')[-1].split('.')[0] if url else None

    def _parse_publish_date(self, publish_time_str: str):
        """解析发布日期"""
        try:
            # 尝试多种格式
            formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%Y年%m月%d日',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(publish_time_str[:10], fmt).date()
                except:
                    pass
            
            # 如果包含"今天"或"昨天"等相对时间
            if '今天' in publish_time_str or '刚刚' in publish_time_str:
                return datetime.now().date()
            elif '昨天' in publish_time_str:
                return (datetime.now() - timedelta(days=1)).date()
            
            return datetime.now().date()
        except:
            return datetime.now().date()

    def _parse_publish_timestamp(self, publish_time_str: str) -> int:
        """解析发布时间戳"""
        try:
            # 尝试多种格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y/%m/%d %H:%M:%S',
                '%Y年%m月%d日 %H:%M:%S',
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(publish_time_str, fmt)
                    return int(dt.timestamp())
                except:
                    pass
            
            return int(datetime.now().timestamp())
        except:
            return int(datetime.now().timestamp())
