import sys
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
from sqlalchemy import select, desc, and_

# Setup paths
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# 1. Load MindSpider config
try:
    import config as mindspider_config
    spider_settings = mindspider_config.settings
    
    # Cleanup config from sys.modules to avoid conflict with MediaCrawler's config
    if 'config' in sys.modules:
        del sys.modules['config']
except ImportError:
    print("Error importing MindSpider config")
    sys.exit(1)

# 2. Setup MediaCrawler path
media_crawler_path = project_root / "DeepSentimentCrawling/MediaCrawler"
sys.path.insert(0, str(media_crawler_path))

# 3. Import MediaCrawler config and overwrite DB settings
try:
    import config as mc_config
    from config import db_config as mc_db_config
    
    # Sync DB config from MindSpider settings
    db_type = spider_settings.DB_DIALECT
    
    # Update SAVE_DATA_OPTION
    mc_config.SAVE_DATA_OPTION = db_type if db_type in ["mysql", "postgresql"] else "db"
    
    # Update DB credentials
    if db_type == "mysql":
        mc_db_config.MYSQL_DB_HOST = spider_settings.DB_HOST
        mc_db_config.MYSQL_DB_PORT = spider_settings.DB_PORT
        mc_db_config.MYSQL_DB_USER = spider_settings.DB_USER
        mc_db_config.MYSQL_DB_PWD = spider_settings.DB_PASSWORD
        mc_db_config.MYSQL_DB_NAME = spider_settings.DB_NAME
        mc_db_config.mysql_db_config.update({
            "host": spider_settings.DB_HOST,
            "port": spider_settings.DB_PORT,
            "user": spider_settings.DB_USER,
            "password": spider_settings.DB_PASSWORD,
            "db_name": spider_settings.DB_NAME,
        })
    elif db_type == "postgresql":
        mc_db_config.POSTGRESQL_DB_HOST = spider_settings.DB_HOST
        mc_db_config.POSTGRESQL_DB_PORT = str(spider_settings.DB_PORT)
        mc_db_config.POSTGRESQL_DB_USER = spider_settings.DB_USER
        mc_db_config.POSTGRESQL_DB_PWD = spider_settings.DB_PASSWORD
        mc_db_config.POSTGRESQL_DB_NAME = spider_settings.DB_NAME
        mc_db_config.postgresql_db_config.update({
            "host": spider_settings.DB_HOST,
            "port": spider_settings.DB_PORT,
            "user": spider_settings.DB_USER,
            "password": spider_settings.DB_PASSWORD,
            "db_name": spider_settings.DB_NAME,
        })

except ImportError as e:
    print(f"Error importing MediaCrawler config: {e}")
    sys.exit(1)

# 4. Import Database modules
from database.models import QbitaiArticle
from database.db_session import get_session

async def get_recent_articles(days=3, limit=5):
    """Fetch recent articles from QbitAI table"""
    async with get_session() as session:
        # Calculate timestamp for 'days' ago
        # QbitaiArticle uses publish_time as BigInteger timestamp (seconds)
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_ts = int(cutoff_date.timestamp())
        
        stmt = (
            select(QbitaiArticle)
            .where(QbitaiArticle.publish_time >= cutoff_ts)
            .order_by(desc(QbitaiArticle.publish_time))
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        articles = result.scalars().all()
        return articles

def format_articles_for_prompt(articles):
    if not articles:
        return "无相关新闻数据。"
    
    formatted = ""
    for i, art in enumerate(articles, 1):
        pub_date = datetime.fromtimestamp(art.publish_time).strftime('%Y-%m-%d %H:%M')
        formatted += f"[{i}] 标题: {art.title}\n"
        formatted += f"    链接: {art.article_url}\n"
        formatted += f"    发布时间: {pub_date}\n"
        formatted += f"    摘要: {art.description}\n"
        # Truncate content to avoid token limit if necessary, but description might be enough
        # Including some content might be better for "Deep Dive"
        content_snippet = art.content[:500].replace('\n', ' ') if art.content else "无内容"
        formatted += f"    内容片段: {content_snippet}...\n\n"
    return formatted

def generate_report(articles, api_key, base_url, model_name):
    if not articles:
        print("没有找到最近的文章，无法生成报告。")
        return None

    # Configure OpenAI client for Gemini
    client = OpenAI(api_key=api_key, base_url=base_url)

    # Read template
    template_path = project_root / "AIReport_example.md"
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except Exception as e:
        print(f"无法读取模版文件: {e}")
        return None

    articles_text = format_articles_for_prompt(articles)
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    prompt = f"""
你是一个专业的AI前沿科技分析师。请根据以下提供的最近几天的量子位(QbitAI)新闻数据，编写一份AI前沿动态速报。

请严格按照以下模版格式和要求生成Markdown内容。
当前的日期是: {today_str}

**模版和要求:**
{template_content}

**新闻数据:**
{articles_text}

**特别指令:**
1. 仅使用提供的新闻数据，请按照模版中的指示处理。
2. 确保"关键数字"、"关键时间"、"背景补充"等深度解读部分有实际依据，不要瞎编。
3. 语言风格要客观、专业、有深度
4. 输出必须是Markdown格式。
5. 忽略模版中的"第二部分：实战演示"内容，只生成你的报告。
6. 参考来源必须使用括号括起来，并且使用英文括号，不要直接使用量子位作为引用，请使用量子位文章里的参考引用，没有则不用添加引用。
"""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Gemini API 调用失败: {e}")
        return None

async def main():
    api_key = spider_settings.REPORT_ENGINE_API_KEY
    base_url = spider_settings.REPORT_ENGINE_BASE_URL
    model_name = spider_settings.REPORT_ENGINE_MODEL_NAME

    if not api_key:
        print("错误: 未在 config.py 或环境变量中配置 REPORT_ENGINE_API_KEY")
        return

    print("正在从数据库获取最近的量子位文章...")
    articles = await get_recent_articles(days=3)
    print(f"获取到 {len(articles)} 篇最近文章。")
    
    if not articles:
        print("无数据，退出。")
        return

    print("正在调用 Gemini 生成报告...")
    report_content = generate_report(articles, api_key, base_url, model_name)
    
    if report_content:
        output_dir = Path(__file__).parent
        output_file = output_dir / f"AI_Report_{datetime.now().strftime('%Y-%m-%d')}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"报告已生成并保存至: {output_file}")
    else:
        print("生成报告失败。")

if __name__ == "__main__":
    asyncio.run(main())

