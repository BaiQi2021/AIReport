import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from crawler.google_ai_scraper import GoogleAIScraper
from crawler.openai_scraper import OpenAIScraper
from crawler.anthropic_scraper import AnthropicScraper
from crawler.meta_microsoft_scraper import MetaAIScraper

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("DateTest")

# Define test range
START_DATE = datetime(2025, 12, 10)
END_DATE = datetime(2025, 12, 19, 23, 59, 59)

async def check_scraper_dates(name, scraper_instance, article_type='blog'):
    logger.info(f"\n--- Testing {name} ---")
    await scraper_instance.init()
    
    try:
        logger.info(f"Fetching list ({article_type})...")
        articles = await scraper_instance.get_article_list(article_type=article_type)
        
        if not articles:
            logger.warning("No articles found in list.")
            return

        logger.info(f"Found {len(articles)} articles. Checking details for top 10...")
        
        checked = 0
        matches = 0
        
        for item in articles[:10]:
            try:
                detail = await scraper_instance.get_article_detail(item['article_id'], item['url'])
                if not detail:
                    logger.warning(f"  Failed to get details for {item['url']}")
                    continue
                
                pub_time = detail.get('publish_time')
                pub_date_str = detail.get('publish_date', 'Unknown')
                title = detail.get('title', 'Unknown')
                
                if not pub_time:
                    logger.warning(f"  [NO DATE] {title[:40]}...")
                    continue
                
                article_dt = datetime.fromtimestamp(pub_time)
                
                # Check condition
                is_match = START_DATE <= article_dt <= END_DATE
                
                icon = "✅" if is_match else "⏭️"
                status = "IN RANGE" if is_match else "OUT OF RANGE"
                
                logger.info(f"  {icon} [{pub_date_str}] {title[:50]}... -> {status}")
                
                checked += 1
                if is_match:
                    matches += 1
                    
            except Exception as e:
                logger.error(f"  Error checking article: {e}")
        
        logger.info(f"Summary for {name}: {matches}/{checked} articles matched date range ({START_DATE.date()} - {END_DATE.date()})")

    finally:
        await scraper_instance.close()

async def main():
    logger.info(f"Target Date Range: {START_DATE.date()} to {END_DATE.date()}\n")
    
    # Google
    await check_scraper_dates("Google AI", GoogleAIScraper(source='google'))
    
    # DeepMind
    await check_scraper_dates("DeepMind", GoogleAIScraper(source='deepmind'))
    
    # OpenAI
    await check_scraper_dates("OpenAI", OpenAIScraper())
    
    # Anthropic
    await check_scraper_dates("Anthropic", AnthropicScraper(), article_type='news')
    
    # Meta
    await check_scraper_dates("Meta AI", MetaAIScraper())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

