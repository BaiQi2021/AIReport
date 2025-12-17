# -*- coding: utf-8 -*-
# @Author  : MindSpider
# @Time    : 2025/12/16
# @Desc    : 量子位爬虫主流程代码

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

from playwright.async_api import BrowserContext, BrowserType, Page, Playwright, async_playwright

import config
from base.base_crawler import AbstractCrawler
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import QbitaiClient
from .help import parse_article_list, parse_article_detail, parse_comments


class QbitaiCrawler(AbstractCrawler):
    """量子位爬虫"""
    context_page: Page
    qbitai_client: QbitaiClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self):
        self.index_url = "https://www.qbitai.com"
        self.user_agent = utils.get_user_agent()
        self.cdp_manager = None

    async def start(self):
        """启动爬虫"""
        async with async_playwright() as playwright:
            # 根据配置选择启动模式
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[QbitaiCrawler] 使用CDP模式启动浏览器")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    None,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[QbitaiCrawler] 使用标准模式启动浏览器")
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium, None, self.user_agent, headless=config.HEADLESS
                )
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)

            # 创建量子位客户端
            self.qbitai_client = await self.create_qbitai_client()

            # 执行爬取
            await self.search()

    async def search(self):
        """搜索并爬取最近两周的文章"""
        utils.logger.info("[QbitaiCrawler] 开始爬取量子位最近两周的文章")
        
        # 计算时间范围：近两周
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        
        utils.logger.info(f"爬取时间范围: {start_date.date()} 到 {end_date.date()}")
        
        # 爬取分页数据
        page = 1
        total_articles = 0
        
        while True:
            utils.logger.info(f"正在爬取第 {page} 页...")
            
            try:
                # 获取文章列表
                articles = await self.qbitai_client.get_article_list(page=page)
                
                if not articles:
                    utils.logger.info("已到达最后一页或没有更多文章")
                    break
                
                for article in articles:
                    # 检查是否在时间范围内
                    article_date = article.get('publish_date')
                    if article_date < start_date.date():
                        utils.logger.info(f"文章日期 {article_date} 超出时间范围，停止爬取")
                        return
                    
                    # 获取完整文章内容
                    try:
                        full_article = await self.qbitai_client.get_article_detail(article['article_id'])
                        if full_article:
                            # 存储文章
                            await self.store_content(full_article)
                            total_articles += 1
                            
                            # 获取评论
                            try:
                                comments = await self.qbitai_client.get_comments(article['article_id'])
                                for comment in comments:
                                    await self.store_comment(comment)
                            except Exception as e:
                                utils.logger.warning(f"获取评论失败: {e}")
                        
                        # 礼貌地延迟
                        await asyncio.sleep(utils.get_random_sleep(1, 3))
                    except Exception as e:
                        utils.logger.error(f"处理文章 {article.get('article_id')} 失败: {e}")
                        continue
                
                page += 1
                # 列表页延迟
                await asyncio.sleep(utils.get_random_sleep(2, 5))
                
            except Exception as e:
                utils.logger.error(f"爬取第 {page} 页失败: {e}")
                break
        
        utils.logger.info(f"爬取完成，共获取 {total_articles} 篇文章")

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """启动浏览器"""
        return await chromium.launch_persistent_context(
            user_data_dir="/tmp/qbitai_browser_data",
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
            proxy=playwright_proxy,
            user_agent=user_agent,
        )

    async def create_qbitai_client(self) -> QbitaiClient:
        """创建量子位客户端"""
        return QbitaiClient(
            playwright_page=self.context_page,
        )

    async def store_content(self, content_item: Dict):
        """存储文章内容"""
        from store import qbitai as qbitai_store
        await qbitai_store.store_article(content_item)

    async def store_comment(self, comment_item: Dict):
        """存储评论"""
        from store import qbitai as qbitai_store
        await qbitai_store.store_comment(comment_item)
