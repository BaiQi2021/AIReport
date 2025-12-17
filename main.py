#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIReport Main Entry Point
1. Crawl QbitAI data
2. Generate Weekly/Daily Report
"""

import asyncio
import argparse
from crawler.qbitai_scraper import run_crawler
from analysis.generator import ReportGenerator
from crawler import utils
from database.db_session import init_db

logger = utils.setup_logger()

async def main():
    parser = argparse.ArgumentParser(description="AIReport Crawler & Generator")
    parser.add_argument("--days", type=int, default=3, help="Number of days to look back for data")
    parser.add_argument("--skip-crawl", action="store_true", help="Skip crawling, only generate report")
    parser.add_argument("--skip-report", action="store_true", help="Skip report generation, only crawl")
    
    args = parser.parse_args()

    # Initialize Database
    logger.info("Initializing Database...")
    await init_db()

    if not args.skip_crawl:
        logger.info("Starting Crawler Phase...")
        await run_crawler(days=args.days)
    
    if not args.skip_report:
        logger.info("Starting Analysis Phase...")
        generator = ReportGenerator()
        await generator.run(days=args.days)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")

