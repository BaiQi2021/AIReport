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
from crawler.constants import DEFAULT_HEADERS

logger = utils.setup_logger()


class BaseWebScraper(ABC):
    """网页爬虫基类"""
    
    def __init__(
        self,
        base_url: str,
        company_name: str,
        use_proxy: bool = False,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        初始化爬虫
        
        Args:
            base_url: 基础URL
            company_name: 公司/来源名称
            use_proxy: 是否使用代理
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url
        self.company_name = company_name
        self.use_proxy = use_proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = DEFAULT_HEADERS.copy()
        self.session: Optional[httpx.AsyncClient] = None
        self.proxy_pool = None
    
    async def init(self):
        """初始化HTTP客户端"""
        kwargs = {
            "headers": self.headers,
            "timeout": self.timeout,
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
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def fetch_page(self, url: str, **kwargs) -> Optional[str]:
        """
        获取页面内容
        
        Args:
            url: 目标URL
            **kwargs: 传递给httpx的额外参数
            
        Returns:
            页面HTML内容，失败返回None
        """
        for attempt in range(self.max_retries):
            try:
                response = await self.session.get(url, **kwargs)
                response.raise_for_status()
                return response.text
            except Exception as e:
                logger.error(f"Failed to fetch page {url} (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                # 如果使用代理且失败，尝试换一个代理
                if self.use_proxy and self.proxy_pool and attempt < self.max_retries - 1:
                    await self._switch_proxy()
                    await asyncio.sleep(2)
                    continue
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
        
        return None
    
    async def _switch_proxy(self):
        """切换代理"""
        try:
            # 标记当前代理失败（简化实现）
            new_proxy_dict = self.proxy_pool.get_proxy_dict()
            if new_proxy_dict:
                await self.session.aclose()
                self.session = httpx.AsyncClient(
                    headers=self.headers,
                    timeout=self.timeout,
                    verify=False,
                    follow_redirects=True,
                    proxies=new_proxy_dict
                )
                logger.info(f"Switched to new proxy")
        except Exception as e:
            logger.error(f"Failed to switch proxy: {e}")
    
    async def fetch_json(self, url: str, **kwargs) -> Optional[Dict]:
        """
        获取JSON数据
        
        Args:
            url: 目标URL
            **kwargs: 传递给httpx的额外参数
            
        Returns:
            JSON数据字典，失败返回None
        """
        try:
            response = await self.session.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch JSON {url}: {e}")
            return None
    
    @abstractmethod
    async def get_article_list(self, page: int = 1) -> List[Dict]:
        """
        获取文章列表（需要子类实现）
        
        Args:
            page: 页码
            
        Returns:
            文章列表
        """
        pass
    
    @abstractmethod
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        """
        获取文章详情（需要子类实现）
        
        Args:
            article_id: 文章ID
            url: 文章URL
            
        Returns:
            文章详情字典，失败返回None
        """
        pass
    
    def extract_article_id(self, url: str) -> Optional[str]:
        """
        从URL中提取文章ID
        
        Args:
            url: 文章URL
            
        Returns:
            文章ID，失败返回None
        """
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
    
    def parse_timestamp(self, time_str: str) -> Optional[int]:
        """
        解析时间字符串为Unix时间戳
        
        Args:
            time_str: 时间字符串
            
        Returns:
            Unix时间戳（秒）；无法解析时返回None
        """
        try:
            if not time_str:
                logger.warning("Publish time missing.")
                return None
            
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
                except ValueError:
                    continue
            
            logger.warning(f"Failed to parse timestamp: {time_str}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing timestamp {time_str}: {e}")
            return None
    
    def extract_reference_links(self, soup: BeautifulSoup, content_elem: Optional[BeautifulSoup]) -> List[Dict]:
        """
        提取文章中的参考链接
        
        Args:
            soup: BeautifulSoup对象
            content_elem: 内容元素
            
        Returns:
            参考链接列表
        """
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
            ref_type = self._classify_reference_link(href)
            if ref_type:
                seen_urls.add(href)
                unique_links.append({
                    'title': text[:200],
                    'url': href,
                    'type': ref_type
                })
        
        logger.info(f"Extracted {len(unique_links)} reference links")
        return unique_links
    
    def _classify_reference_link(self, url: str) -> Optional[str]:
        """
        分类参考链接
        
        Args:
            url: 链接URL
            
        Returns:
            链接类型，不符合条件返回None
        """
        url_lower = url.lower()
        
        # 论文相关
        if any(domain in url_lower for domain in [
            'arxiv.org', 'paperswithcode.com', 'semanticscholar.org',
            'acm.org', 'ieee.org', 'nature.com', 'science.org'
        ]):
            return 'paper'
        
        # GitHub/代码仓库
        elif any(domain in url_lower for domain in [
            'github.com', 'gitlab.com', 'huggingface.co'
        ]):
            return 'code'
        
        # AI公司官方网站
        elif any(domain in url_lower for domain in [
            'openai.com', 'anthropic.com', 'google.com', 'microsoft.com',
            'meta.com', 'nvidia.com', 'apple.com', 'deepmind.com',
            'baidu.com', 'alibaba.com'
        ]):
            return 'official'
        
        # 技术博客
        elif any(domain in url_lower for domain in [
            'blog.', 'medium.com', 'towardsdatascience.com', 'hackernoon.com'
        ]):
            return 'blog'
        
        # 社交媒体
        elif any(domain in url_lower for domain in [
            'twitter.com', 'x.com', 'zhihu.com', 'youtube.com', 'bilibili.com'
        ]):
            # 排除分享按钮
            if not any(k in url_lower for k in ['share', 'intent/tweet', 'sharer']):
                return 'social'
        
        # 其他外部链接
        elif url.startswith('http'):
            return 'external'
        
        return None
    
    def clean_text(self, text: str) -> str:
        """
        清理文本
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ''
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def parse_tags(self, tag_elements) -> str:
        """
        解析标签
        
        Args:
            tag_elements: 标签元素列表
            
        Returns:
            JSON格式的标签字符串
        """
        tags = []
        for tag_elem in tag_elements:
            tag_text = tag_elem.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)
        return json.dumps(tags, ensure_ascii=False) if tags else ''
