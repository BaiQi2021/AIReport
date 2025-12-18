#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base Web Scraper
通用的网页爬虫基类，提供基础功能
"""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from crawler import utils

logger = utils.setup_logger()


class BaseWebScraper(ABC):
    """网页爬虫基类"""
    
    def __init__(self, base_url: str, company_name: str, use_proxy: bool = False):
        self.base_url = base_url
        self.company_name = company_name
        self.use_proxy = use_proxy
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        self.session = None
        self.proxy_pool = None
    
    async def init(self):
        """初始化HTTP客户端"""
        kwargs = {
            "headers": self.headers,
            "timeout": 30,
            "verify": False,
            "follow_redirects": True
        }
        
        # 如果启用代理，尝试获取代理
        if self.use_proxy:
            from crawler.proxy_pool import get_global_proxy_pool
            self.proxy_pool = get_global_proxy_pool()
            proxy_dict = self.proxy_pool.get_proxy_dict()
            if proxy_dict:
                kwargs["proxies"] = proxy_dict
                logger.info(f"Using proxy for {self.company_name}")
        
        self.session = httpx.AsyncClient(**kwargs)
    
    async def close(self):
        """关闭HTTP客户端"""
        if self.session:
            await self.session.aclose()
    
    async def fetch_page(self, url: str, **kwargs) -> Optional[str]:
        """获取页面内容"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.session.get(url, **kwargs)
                response.raise_for_status()
                return response.text
            except Exception as e:
                logger.error(f"Failed to fetch page {url} (attempt {attempt + 1}/{max_retries}): {e}")
                
                # 如果使用代理且失败，尝试换一个代理
                if self.use_proxy and self.proxy_pool and attempt < max_retries - 1:
                    # 标记当前代理失败
                    current_proxy = self.session._transport._pool._proxy_url if hasattr(self.session, '_transport') else None
                    if current_proxy:
                        self.proxy_pool.mark_failed(str(current_proxy))
                    
                    # 获取新代理
                    new_proxy_dict = self.proxy_pool.get_proxy_dict()
                    if new_proxy_dict:
                        await self.session.aclose()
                        self.session = httpx.AsyncClient(
                            headers=self.headers,
                            timeout=30,
                            verify=False,
                            follow_redirects=True,
                            proxies=new_proxy_dict
                        )
                        logger.info(f"Switched to new proxy, retrying...")
                        await asyncio.sleep(2)
                        continue
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                
        return None
    
    async def fetch_json(self, url: str, **kwargs) -> Optional[Dict]:
        """获取JSON数据"""
        try:
            response = await self.session.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch JSON {url}: {e}")
            return None
    
    @abstractmethod
    async def get_article_list(self, page: int = 1) -> List[Dict]:
        """获取文章列表（需要子类实现）"""
        pass
    
    @abstractmethod
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """获取文章详情（需要子类实现）"""
        pass
    
    def extract_article_id(self, url: str) -> Optional[str]:
        """从URL中提取文章ID"""
        patterns = [
            r'/article[s]?/([^/\?]+)',
            r'/post[s]?/([^/\?]+)',
            r'/blog/([^/\?]+)',
            r'/news/([^/\?]+)',
            r'/research/([^/\?]+)',
            r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',  # UUID
            r'/(\d+)',  # 纯数字ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # 如果都匹配不到，使用URL的最后一部分
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if path_parts:
            return path_parts[-1].split('.')[0]
        
        return None
    
    def parse_timestamp(self, time_str: str) -> int:
        """解析时间字符串为Unix时间戳"""
        try:
            if not time_str:
                return int(datetime.now().timestamp())
            
            time_str = time_str.strip()
            now = datetime.now()
            
            # 处理相对时间
            if any(keyword in time_str.lower() for keyword in ['just now', '刚刚', 'now']):
                return int(now.timestamp())
            
            # 分钟前
            if re.search(r'(\d+)\s*(minute|min|分钟)', time_str, re.I):
                match = re.search(r'(\d+)', time_str)
                minutes = int(match.group(1)) if match else 0
                return int((now - timedelta(minutes=minutes)).timestamp())
            
            # 小时前
            if re.search(r'(\d+)\s*(hour|hr|小时)', time_str, re.I):
                match = re.search(r'(\d+)', time_str)
                hours = int(match.group(1)) if match else 0
                return int((now - timedelta(hours=hours)).timestamp())
            
            # 天前
            if re.search(r'(\d+)\s*(day|天)', time_str, re.I):
                match = re.search(r'(\d+)', time_str)
                days = int(match.group(1)) if match else 0
                return int((now - timedelta(days=days)).timestamp())
            
            # 昨天/前天
            if '昨天' in time_str or 'yesterday' in time_str.lower():
                return int((now - timedelta(days=1)).timestamp())
            if '前天' in time_str:
                return int((now - timedelta(days=2)).timestamp())
            
            # ISO 8601格式
            if 'T' in time_str and 'Z' in time_str:
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                return int(dt.timestamp())
            
            # 标准日期格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%dT%H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%Y年%m月%d日 %H:%M:%S',
                '%Y年%m月%d日',
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%B %d, %Y',  # January 1, 2024
                '%b %d, %Y',  # Jan 1, 2024
                '%d %B %Y',   # 1 January 2024
                '%d %b %Y',   # 1 Jan 2024
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(time_str[:25], fmt)
                    return int(dt.timestamp())
                except:
                    continue
            
            logger.warning(f"Failed to parse timestamp: {time_str}")
            return int(now.timestamp())
            
        except Exception as e:
            logger.error(f"Error parsing timestamp {time_str}: {e}")
            return int(datetime.now().timestamp())
    
    def extract_reference_links(self, soup: BeautifulSoup, content_elem: Optional[BeautifulSoup]) -> List[Dict]:
        """提取文章中的参考链接"""
        reference_links = []
        
        if not content_elem:
            return reference_links
        
        candidates = []
        
        # 1. 提取<a>标签中的链接
        for link in content_elem.find_all('a', href=True):
            href = link.get('href', '').strip()
            text = link.get_text(strip=True)
            if href:
                candidates.append((href, text or href))
        
        # 2. 提取文本内容中的链接
        text_content = content_elem.get_text()
        url_pattern = re.compile(r'https?://[^\s<>\[\]"\'\u4e00-\u9fa5]+')
        text_urls = url_pattern.findall(text_content)
        
        for url in text_urls:
            url = url.rstrip('.,;:。，；：')
            candidates.append((url, url))
        
        # 去重和过滤
        seen_urls = set()
        unique_links = []
        
        for href, text in candidates:
            if not href:
                continue
            
            # 补全相对路径
            if not href.startswith('http'):
                href = urljoin(self.base_url, href)
            
            if href in seen_urls:
                continue
            
            # 过滤掉自身网站的链接
            base_domain = urlparse(self.base_url).netloc
            href_domain = urlparse(href).netloc
            if base_domain in href_domain:
                continue
            
            # 识别参考来源
            is_reference = False
            ref_type = 'other'
            href_lower = href.lower()
            
            # 论文相关
            if any(domain in href_lower for domain in ['arxiv.org', 'paperswithcode.com', 'semanticscholar.org', 'acm.org', 'ieee.org', 'nature.com', 'science.org']):
                is_reference = True
                ref_type = 'paper'
            # GitHub/代码仓库
            elif any(domain in href_lower for domain in ['github.com', 'gitlab.com', 'huggingface.co']):
                is_reference = True
                ref_type = 'code'
            # AI公司官方网站
            elif any(domain in href_lower for domain in ['openai.com', 'anthropic.com', 'google.com', 'microsoft.com', 'meta.com', 'nvidia.com', 'apple.com', 'deepmind.com', 'baidu.com', 'alibaba.com']):
                is_reference = True
                ref_type = 'official'
            # 技术博客
            elif any(domain in href_lower for domain in ['blog.', 'medium.com', 'towardsdatascience.com', 'hackernoon.com']):
                is_reference = True
                ref_type = 'blog'
            # 社交媒体
            elif any(domain in href_lower for domain in ['twitter.com', 'x.com', 'zhihu.com', 'youtube.com', 'bilibili.com']):
                if not any(k in href_lower for k in ['share', 'intent/tweet', 'sharer']):
                    is_reference = True
                    ref_type = 'social'
            # 其他外部链接
            elif href.startswith('http'):
                is_reference = True
                ref_type = 'external'
            
            if is_reference:
                seen_urls.add(href)
                unique_links.append({
                    'title': text[:200],
                    'url': href,
                    'type': ref_type
                })
        
        logger.info(f"Extracted {len(unique_links)} reference links")
        return unique_links
    
    def clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ''
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def parse_tags(self, tag_elements) -> str:
        """解析标签"""
        tags = []
        for tag_elem in tag_elements:
            tag_text = tag_elem.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)
        return json.dumps(tags, ensure_ascii=False) if tags else ''

