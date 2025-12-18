#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Crawler Scheduler
统一的爬虫调度器，管理所有爬虫的执行
"""

import asyncio
from datetime import datetime
from typing import Dict, List

from crawler import utils
from crawler.crawler_config import (
    get_enabled_company_crawlers,
    get_enabled_news_crawlers,
    DEFAULT_CRAWLER_CONFIG
)

# 导入各个爬虫
from crawler.qbitai_scraper import run_crawler as run_qbitai_crawler
from crawler.openai_scraper import run_openai_crawler
from crawler.anthropic_scraper import run_anthropic_crawler
from crawler.google_ai_scraper import run_google_ai_crawler
from crawler.china_ai_scraper import run_china_ai_crawler
from crawler.meta_microsoft_scraper import run_meta_microsoft_crawler
from crawler.news_scraper import run_jiqizhixin_crawler, run_xinzhiyuan_crawler

logger = utils.setup_logger()


class CrawlerScheduler:
    """爬虫调度器"""
    
    def __init__(self, days: int = 7):
        self.days = days
        self.results = {
            'total_crawlers': 0,
            'success_crawlers': 0,
            'failed_crawlers': 0,
            'crawlers': []
        }
    
    async def run_company_crawlers(self):
        """运行所有启用的公司爬虫"""
        enabled_crawlers = get_enabled_company_crawlers()
        
        logger.info("=" * 80)
        logger.info(f"📊 Found {len(enabled_crawlers)} enabled company crawlers")
        logger.info("=" * 80)
        
        for crawler_config in enabled_crawlers:
            crawler_key = crawler_config['key']
            crawler_name = crawler_config['name']
            
            self.results['total_crawlers'] += 1
            
            try:
                logger.info("")
                logger.info("🎯 " + "=" * 70)
                logger.info(f"   Starting crawler: {crawler_name} ({crawler_key})")
                logger.info("   " + "=" * 70)
                
                start_time = datetime.now()
                
                # 根据爬虫类型调用对应的爬虫函数
                if crawler_key == 'openai':
                    await run_openai_crawler(days=self.days)
                elif crawler_key == 'anthropic':
                    await run_anthropic_crawler(days=self.days)
                elif crawler_key == 'google':
                    await run_google_ai_crawler(days=self.days)
                elif crawler_key in ['zhipu', 'alibaba', 'moonshot']:
                    # 国内AI公司使用同一个爬虫模块
                    await run_china_ai_crawler(days=self.days)
                elif crawler_key in ['meta', 'microsoft']:
                    await run_meta_microsoft_crawler(days=self.days)
                else:
                    logger.warning(f"No crawler implementation found for: {crawler_key}")
                    continue
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                self.results['success_crawlers'] += 1
                self.results['crawlers'].append({
                    'name': crawler_name,
                    'key': crawler_key,
                    'status': 'success',
                    'duration': duration
                })
                
                logger.info(f"✅ Crawler {crawler_name} completed in {duration:.2f}s")
                
                # 爬虫之间的延迟
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ Crawler {crawler_name} failed: {e}")
                self.results['failed_crawlers'] += 1
                self.results['crawlers'].append({
                    'name': crawler_name,
                    'key': crawler_key,
                    'status': 'failed',
                    'error': str(e)
                })
                continue
    
    async def run_news_crawlers(self):
        """运行所有启用的新闻爬虫"""
        enabled_crawlers = get_enabled_news_crawlers()
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📰 Found {len(enabled_crawlers)} enabled news crawlers")
        logger.info("=" * 80)
        
        for crawler_config in enabled_crawlers:
            crawler_key = crawler_config['key']
            crawler_name = crawler_config['name']
            crawler_type = crawler_config.get('crawler_type', 'generic')
            
            self.results['total_crawlers'] += 1
            
            try:
                logger.info("")
                logger.info("🎯 " + "=" * 70)
                logger.info(f"   Starting news crawler: {crawler_name} ({crawler_key})")
                logger.info("   " + "=" * 70)
                
                start_time = datetime.now()
                
                # 根据爬虫类型调用对应的爬虫
                if crawler_key == 'qbitai':
                    await run_qbitai_crawler(days=self.days)
                elif crawler_key == 'jiqizhixin':
                    await run_jiqizhixin_crawler(days=self.days)
                elif crawler_key == 'xinzhiyuan':
                    await run_xinzhiyuan_crawler(days=self.days)
                elif crawler_type == 'generic':
                    logger.warning(f"Generic crawler not yet implemented for: {crawler_key}")
                    continue
                else:
                    logger.warning(f"Unknown crawler type for: {crawler_key}")
                    continue
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                self.results['success_crawlers'] += 1
                self.results['crawlers'].append({
                    'name': crawler_name,
                    'key': crawler_key,
                    'status': 'success',
                    'duration': duration
                })
                
                logger.info(f"✅ News crawler {crawler_name} completed in {duration:.2f}s")
                
                # 爬虫之间的延迟
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ News crawler {crawler_name} failed: {e}")
                self.results['failed_crawlers'] += 1
                self.results['crawlers'].append({
                    'name': crawler_name,
                    'key': crawler_key,
                    'status': 'failed',
                    'error': str(e)
                })
                continue
    
    async def run_all(self):
        """运行所有爬虫"""
        logger.info("🚀" * 40)
        logger.info("   AI REPORT - UNIFIED CRAWLER SCHEDULER")
        logger.info("🚀" * 40)
        logger.info(f"📅 Date Range: Last {self.days} days")
        logger.info(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")
        
        overall_start = datetime.now()
        
        # 运行公司爬虫
        await self.run_company_crawlers()
        
        # 运行新闻爬虫
        await self.run_news_crawlers()
        
        overall_end = datetime.now()
        overall_duration = (overall_end - overall_start).total_seconds()
        
        # 打印总结
        self.print_summary(overall_duration)
    
    def print_summary(self, total_duration: float):
        """打印爬虫执行摘要"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 CRAWLER EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Crawlers: {self.results['total_crawlers']}")
        logger.info(f"✅ Success: {self.results['success_crawlers']}")
        logger.info(f"❌ Failed: {self.results['failed_crawlers']}")
        logger.info(f"⏱️  Total Duration: {total_duration:.2f}s ({total_duration/60:.2f} minutes)")
        logger.info("")
        
        if self.results['crawlers']:
            logger.info("Crawler Details:")
            logger.info("-" * 80)
            for crawler in self.results['crawlers']:
                status_icon = "✅" if crawler['status'] == 'success' else "❌"
                if crawler['status'] == 'success':
                    logger.info(f"{status_icon} {crawler['name']:20} | Duration: {crawler.get('duration', 0):.2f}s")
                else:
                    logger.info(f"{status_icon} {crawler['name']:20} | Error: {crawler.get('error', 'Unknown')}")
        
        logger.info("=" * 80)
        logger.info(f"⏰ End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("🎉 All crawlers completed!")
        logger.info("=" * 80)


async def run_all_crawlers(days: int = 7):
    """运行所有爬虫的便捷函数"""
    scheduler = CrawlerScheduler(days=days)
    await scheduler.run_all()
    return scheduler.results


if __name__ == "__main__":
    asyncio.run(run_all_crawlers(days=7))

