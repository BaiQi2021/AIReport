#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIReport Main Entry Point
1. Crawl AI company websites and news sites
2. Generate Weekly/Daily Report
"""

import asyncio
import argparse
from crawler.scheduler import run_all_crawlers
from crawler.advanced_scheduler import run_all_crawlers_concurrent
from analysis.generator import ReportGenerator
from crawler import utils
from database.db_session import init_db

logger = utils.setup_logger()

async def main():
    parser = argparse.ArgumentParser(description="AIReport Crawler & Generator")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back for data")
    parser.add_argument("--skip-crawl", action="store_true", help="Skip crawling, only generate report")
    parser.add_argument("--skip-report", action="store_true", help="Skip report generation, only crawl")
    parser.add_argument("--crawler", type=str, default="all", 
                        help="Specify crawler: all, qbitai, openai, anthropic, google, china, meta, microsoft, news, company")
    parser.add_argument("--concurrent", action="store_true", help="Enable concurrent crawling (faster)")
    parser.add_argument("--max-concurrent", type=int, default=3, help="Maximum concurrent crawlers (default: 3)")
    parser.add_argument("--no-incremental", action="store_true", help="Disable incremental updates")
    parser.add_argument("--use-proxy", action="store_true", help="Enable proxy pool")
    
    args = parser.parse_args()

    # Initialize Database
    logger.info("Initializing Database...")
    await init_db()
    
    # Initialize Proxy Pool if enabled
    if args.use_proxy:
        logger.info("Proxy support enabled (configure proxies in proxy_pool.py)")
        # TODO: Load proxies from config file or API

    if not args.skip_crawl:
        logger.info("Starting Crawler Phase...")
        
        # 选择调度器：并发或串行
        if args.concurrent:
            logger.info(f"🚀 Using CONCURRENT scheduler (max: {args.max_concurrent})")
            if args.crawler == "all":
                await run_all_crawlers_concurrent(
                    days=args.days,
                    max_concurrent=args.max_concurrent,
                    use_incremental=not args.no_incremental
                )
            else:
                logger.warning("Concurrent mode only works with --crawler all. Using sequential mode.")
                await run_single_crawler(args.crawler, args.days)
        else:
            logger.info("📝 Using SEQUENTIAL scheduler")
            if args.crawler == "all":
                await run_all_crawlers(days=args.days)
            else:
                await run_single_crawler(args.crawler, args.days)
    
    if not args.skip_report:
        logger.info("Starting Analysis Phase...")
        generator = ReportGenerator()
        await generator.run(days=args.days)


async def run_single_crawler(crawler_name: str, days: int):
    """运行单个爬虫"""
    if crawler_name == "qbitai":
        from crawler.qbitai_scraper import run_crawler
        await run_crawler(days=days)
    elif crawler_name == "openai":
        from crawler.openai_scraper import run_openai_crawler
        await run_openai_crawler(days=days)
    elif crawler_name == "anthropic":
        from crawler.anthropic_scraper import run_anthropic_crawler
        await run_anthropic_crawler(days=days)
    elif crawler_name == "google":
        from crawler.google_ai_scraper import run_google_ai_crawler
        await run_google_ai_crawler(days=days)
    elif crawler_name == "china":
        from crawler.china_ai_scraper import run_china_ai_crawler
        await run_china_ai_crawler(days=days)
    elif crawler_name == "meta":
        from crawler.meta_microsoft_scraper import run_meta_microsoft_crawler
        await run_meta_microsoft_crawler(days=days)
    elif crawler_name == "microsoft":
        from crawler.meta_microsoft_scraper import run_meta_microsoft_crawler
        await run_meta_microsoft_crawler(days=days)
    elif crawler_name == "jiqizhixin":
        from crawler.news_scraper import run_jiqizhixin_crawler
        await run_jiqizhixin_crawler(days=days)
    elif crawler_name == "xinzhiyuan":
        from crawler.news_scraper import run_xinzhiyuan_crawler
        await run_xinzhiyuan_crawler(days=days)
    elif crawler_name == "company":
        from crawler.scheduler import CrawlerScheduler
        scheduler = CrawlerScheduler(days=days)
        await scheduler.run_company_crawlers()
    elif crawler_name == "news":
        from crawler.scheduler import CrawlerScheduler
        scheduler = CrawlerScheduler(days=days)
        await scheduler.run_news_crawlers()
    else:
        logger.error(f"Unknown crawler: {crawler_name}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")

