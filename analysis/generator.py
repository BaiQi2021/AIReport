import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
import httpx
from sqlalchemy import select, desc

from database.models import QbitaiArticle
from database.db_session import get_session
import config
from crawler import utils

settings = config.settings
logger = utils.logger

class ReportGenerator:
    def __init__(self):
        self.api_key = settings.REPORT_ENGINE_API_KEY or settings.GEMINI_API_KEY
        self.base_url = settings.REPORT_ENGINE_BASE_URL or settings.GEMINI_BASE_URL
        self.model_name = settings.REPORT_ENGINE_MODEL_NAME or settings.GEMINI_MODEL_NAME
        
        if not self.api_key:
            logger.warning("API Key not configured. Report generation will fail.")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.template_path = Path(__file__).parent / "templates" / "AIReport_example.md"

    async def get_recent_articles(self, days=3, limit=20) -> List[QbitaiArticle]:
        """Fetch recent articles from database."""
        async with get_session() as session:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_ts = int(cutoff_date.timestamp())
            
            stmt = (
                select(QbitaiArticle)
                .where(QbitaiArticle.publish_time >= cutoff_ts)
                .order_by(desc(QbitaiArticle.publish_time))
                .limit(limit)
            )
            
            result = await session.execute(stmt)
            return result.scalars().all()

    def format_articles_for_prompt(self, articles: List[QbitaiArticle]) -> str:
        if not articles:
            return "无相关新闻数据。"
        
        formatted = ""
        for i, art in enumerate(articles, 1):
            pub_date = datetime.fromtimestamp(art.publish_time).strftime('%Y-%m-%d %H:%M')
            formatted += f"[{i}] 标题: {art.title}\n"
            formatted += f"    量子位链接: {art.article_url}\n"
            formatted += f"    发布时间: {pub_date}\n"
            formatted += f"    摘要: {art.description}\n"
            content_snippet = art.content[:500].replace('\n', ' ') if art.content else "无内容"
            formatted += f"    内容片段: {content_snippet}...\n"
            
            # 添加参考链接信息
            if art.reference_links:
                try:
                    import json
                    ref_links = json.loads(art.reference_links)
                    if ref_links:
                        formatted += f"    原始参考来源:\n"
                        for ref in ref_links:
                            formatted += f"      - [{ref['title']}]({ref['url']}) (类型: {ref['type']})\n"
                except:
                    pass
            
            formatted += "\n"
        return formatted

    def generate_report_content(self, articles: List[QbitaiArticle]) -> Optional[str]:
        if not articles:
            logger.warning("No articles found to generate report.")
            return None

        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read template: {e}")
            return None

        articles_text = self.format_articles_for_prompt(articles)
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
1. 仅使用提供的新闻数据，请按照模版中的指示处理，一级标题和二级标题必须与模版一致。
2. 确保"关键数字"、"关键时间"、"背景补充"等深度解读部分有实际依据，不要瞎编。
3. 语言风格要客观、专业、有深度
4. 输出必须是Markdown格式。
5. 三级标题基于记忆分析总结生成，生成个性化的报告。

6. **【核心要求】深度解读部分必须详细充实：**
   - **每条新闻的深度解读至少包含 5-8 个维度**
   - **每个维度至少 2-3 个要点**，不要只写一句话
   - 必须深入挖掘新闻内容中的：
     * 技术细节（算法、架构、性能指标）
     * 商业价值（市场定位、竞争优势、商业模式）
     * 行业影响（对上下游的影响、竞争格局变化）
     * 背景分析（为什么现在做、解决了什么痛点）
   - **去营销化**：必须客观分析局限性和挑战，不能只说优点
   - 示例：
     * ❌ 差："技术突破：使用了新方法"
     * ✅ 好："技术突破：采用双向解耦架构打破了传统归一化流必须可逆的限制，允许使用更通用的 Transformer 架构，在保持生成质量的同时将推理速度提升了 40%，且模型设计灵活性大幅提高"

7. **【重要】深度解读各维度填充规则：**
   - **💡 核心亮点**：必填，至少 2 个要点，说明"是什么" + "为什么重要"
   - **🔬 技术/方法突破**：技术类新闻必填，至少 2 个要点，说明创新点和对比优势
   - **📊 关键数字**：尽量多挖掘，包括性能、规模、时间、成本、对比数据
   - **📅 关键时间**：有则填，包括发布时间、里程碑、未来计划
   - **🎯 应用场景**：应用/产品类新闻必填，说明具体用途和目标用户
   - **📝 背景与细节**：必填，至少 3-5 个要点，深入分析行业背景、竞争对手、技术演进
   - **🌍 影响分析**：必填，至少 2-3 个维度，分析对行业、市场、用户的影响
   - **⚠️ 局限性与挑战**：尽量填写，体现客观分析，去营销化
   - **💬 金句摘录**：有原文引用则填

8. **【重要】参考来源引用规则：**
   - **标题链接**：
     * **优先使用**：如果新闻数据中提供了"原始参考来源"（如论文、GitHub、官方博客），**必须**使用该原始来源的 URL 作为文章标题的链接。
     * **次选**：只有当没有原始参考来源时，不需要添加链接。
   - **来源字段 (Source)**：
     * **优先填写**：原始来源的名称（例如：OpenAI, Google, arXiv, Nature, Hugging Face 等）。
     * **次选**：只有当没有原始参考来源时，不填写。
   - **引用格式**：
     * **[文章标题](原始来源URL)** (来源: `原始来源名称`, 日期: `...`)
   - **文中引用**：
     * 在深度解读中提到具体技术、论文或代码时，再次引用原始来源链接。
     * 示例：根据论文 ([论文标题](arxiv链接))，该方法...
   - **禁止**：
     * 如果有原始来源，**禁止**在标题链接或来源字段中使用量子位链接/名称。
     * 不要虚构不存在的原始来源。

9. **【质量检查清单】生成完成后自查：**
   - ✅ 每条新闻的深度解读是否有 50-100+ 字？
   - ✅ 是否充分挖掘了新闻中的数字、时间、人物、技术细节？
   - ✅ 是否分析了行业背景和竞争格局？
   - ✅ 是否客观指出了局限性（而不是一味吹捧）？
   - ✅ 技术类新闻是否说明了技术原理和创新点？

"""

        try:
            logger.info(f"Sending request to LLM ({self.model_name})...")
            # Create a new client with verify=False specifically for macOS issues
            client = OpenAI(
                api_key=self.api_key, 
                base_url=self.base_url,
                http_client=httpx.Client(verify=False)
            )
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM API Call failed: {e}")
            return None

    async def run(self, days=3):
        logger.info("Fetching articles for report...")
        articles = await self.get_recent_articles(days=days)
        logger.info(f"Found {len(articles)} articles.")
        
        if not articles:
            return

        report_content = self.generate_report_content(articles)
        
        if report_content:
            output_dir = Path("final_reports")
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / f"AI_Report_{datetime.now().strftime('%Y-%m-%d')}.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Report saved to: {output_file}")
        else:
            logger.error("Failed to generate report.")

if __name__ == "__main__":
    generator = ReportGenerator()
    asyncio.run(generator.run())

