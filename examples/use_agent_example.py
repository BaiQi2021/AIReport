#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeminiAIReportAgent 使用示例
演示如何在代码中使用 Agent
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def example_1_basic_usage():
    """
    示例1：基本使用
    """
    print("=" * 60)
    print("示例1：基本使用")
    print("=" * 60)
    
    from analysis.gemini_agent import GeminiAIReportAgent
    
    # 初始化 Agent
    agent = GeminiAIReportAgent(max_retries=2)
    
    # 运行完整流程
    report_content = await agent.run(
        days=3,                  # 获取最近3天的数据
        save_intermediate=True   # 保存中间结果
    )
    
    if report_content:
        print("✓ 报告生成成功")
        print(f"报告长度: {len(report_content)} 字符")
    else:
        print("✗ 报告生成失败")


async def example_2_step_by_step():
    """
    示例2：分步执行
    """
    print("\n" + "=" * 60)
    print("示例2：分步执行")
    print("=" * 60)
    
    from analysis.gemini_agent import GeminiAIReportAgent
    
    # 初始化 Agent
    agent = GeminiAIReportAgent(max_retries=2)
    
    # 1. 获取数据
    print("\n[1/5] 获取数据...")
    news_items = await agent.fetch_articles_from_db(days=3, limit=50)
    print(f"✓ 获取到 {len(news_items)} 条新闻")
    
    # 2. 过滤
    print("\n[2/5] 过滤噪音...")
    news_items = await agent.step1_filter(news_items, batch_size=20)
    print(f"✓ 保留 {len(news_items)} 条新闻")
    
    # 3. 归类
    print("\n[3/5] 事件归类...")
    news_items = await agent.step2_cluster(news_items, batch_size=30)
    
    # 统计事件数
    from collections import defaultdict
    events = defaultdict(list)
    for item in news_items:
        events[item.event_id].append(item)
    print(f"✓ 识别出 {len(events)} 个独立事件")
    
    # 4. 去重
    print("\n[4/5] 去重...")
    news_items = await agent.step3_deduplicate(news_items)
    print(f"✓ 去重后保留 {len(news_items)} 条新闻")
    
    # 5. 排序
    print("\n[5/5] 价值评分...")
    news_items = await agent.step4_rank(news_items, batch_size=20)
    
    # 统计各级别数量
    level_counts = defaultdict(int)
    for item in news_items:
        level_counts[item.ranking_level] += 1
    
    print(f"✓ 评分完成:")
    print(f"  S级: {level_counts['S']} 条")
    print(f"  A级: {level_counts['A']} 条")
    print(f"  B级: {level_counts['B']} 条")
    print(f"  C级: {level_counts['C']} 条")
    
    # 6. 生成报告
    print("\n[6/6] 生成报告...")
    report_content = agent.generate_final_report(news_items, quality_check=True)
    
    if report_content:
        print("✓ 报告生成成功")
        
        # 保存报告
        from datetime import datetime
        output_file = project_root / "final_reports" / f"Example_Report_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.md"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"报告已保存: {output_file}")
    else:
        print("✗ 报告生成失败")


async def example_3_custom_filtering():
    """
    示例3：自定义过滤逻辑
    """
    print("\n" + "=" * 60)
    print("示例3：自定义过滤逻辑")
    print("=" * 60)
    
    from analysis.gemini_agent import GeminiAIReportAgent
    
    agent = GeminiAIReportAgent()
    
    # 获取数据
    news_items = await agent.fetch_articles_from_db(days=3, limit=30)
    print(f"获取到 {len(news_items)} 条新闻")
    
    # 自定义过滤：只保留来自官方来源的新闻
    official_sources = ["OPENAI", "ANTHROPIC", "GOOGLE", "META", "MICROSOFT"]
    
    filtered_items = []
    for item in news_items:
        if item.source.upper() in official_sources:
            filtered_items.append(item)
    
    print(f"过滤后（仅官方来源）: {len(filtered_items)} 条新闻")
    
    # 继续后续处理
    if filtered_items:
        news_items = await agent.step2_cluster(filtered_items)
        news_items = await agent.step3_deduplicate(news_items)
        news_items = await agent.step4_rank(news_items)
        
        print(f"\n最终保留: {len(news_items)} 条新闻")
        
        # 显示前3条
        print("\n前3条新闻:")
        for i, item in enumerate(news_items[:3], 1):
            print(f"  {i}. [{item.ranking_level}] {item.title[:50]}...")
            print(f"     来源: {item.source}, 评分: {item.final_score:.2f}")


async def example_4_analyze_results():
    """
    示例4：分析处理结果
    """
    print("\n" + "=" * 60)
    print("示例4：分析处理结果")
    print("=" * 60)
    
    from analysis.gemini_agent import GeminiAIReportAgent
    from collections import defaultdict
    
    agent = GeminiAIReportAgent()
    
    # 运行完整流程并保存中间结果
    await agent.run(days=3, save_intermediate=True)
    
    # 读取中间结果进行分析
    import json
    intermediate_dir = project_root / "final_reports" / "intermediate"
    
    if intermediate_dir.exists():
        json_files = sorted(intermediate_dir.glob("*.json"))
        
        if json_files:
            # 读取最新的排序结果
            latest_ranked = [f for f in json_files if f.name.startswith("04_ranked")]
            
            if latest_ranked:
                with open(latest_ranked[-1], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                print(f"\n分析文件: {latest_ranked[-1].name}")
                print(f"总新闻数: {len(data)}")
                
                # 统计各来源的新闻数量
                source_counts = defaultdict(int)
                for item in data:
                    source_counts[item['source']] += 1
                
                print("\n各来源新闻数量:")
                for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {source}: {count} 条")
                
                # 统计各级别的平均分数
                level_scores = defaultdict(list)
                for item in data:
                    level_scores[item['ranking_level']].append(item['final_score'])
                
                print("\n各级别平均分数:")
                for level in ['S', 'A', 'B', 'C']:
                    if level in level_scores:
                        avg_score = sum(level_scores[level]) / len(level_scores[level])
                        print(f"  {level}级: {avg_score:.2f} ({len(level_scores[level])} 条)")
                
                # 找出最高分的新闻
                top_news = max(data, key=lambda x: x['final_score'])
                print(f"\n最高分新闻:")
                print(f"  标题: {top_news['title']}")
                print(f"  评分: {top_news['final_score']:.2f}")
                print(f"  来源: {top_news['source']}")
                print(f"  级别: {top_news['ranking_level']}")
            else:
                print("未找到排序结果文件")
        else:
            print("未找到中间结果文件")
    else:
        print("中间结果目录不存在")


async def example_5_error_handling():
    """
    示例5：错误处理
    """
    print("\n" + "=" * 60)
    print("示例5：错误处理")
    print("=" * 60)
    
    from analysis.gemini_agent import GeminiAIReportAgent
    
    try:
        # 初始化 Agent
        agent = GeminiAIReportAgent(max_retries=3)
        
        # 运行流程
        report_content = await agent.run(days=3)
        
        if report_content:
            print("✓ 报告生成成功")
        else:
            print("✗ 报告生成失败，但没有抛出异常")
            
    except ValueError as e:
        print(f"✗ 配置错误: {e}")
        print("提示：请检查 .env 文件中的 API Key 配置")
        
    except Exception as e:
        print(f"✗ 运行错误: {e}")
        print("提示：请检查网络连接和 API 配额")


async def main():
    """主函数"""
    import argparse
    
    # 初始化数据库
    from database.db_session import init_db
    await init_db()
    
    parser = argparse.ArgumentParser(description="GeminiAIReportAgent 使用示例")
    parser.add_argument("--example", type=str, default="1",
                       choices=["1", "2", "3", "4", "5", "all"],
                       help="选择要运行的示例")
    
    args = parser.parse_args()
    
    examples = {
        "1": example_1_basic_usage,
        "2": example_2_step_by_step,
        "3": example_3_custom_filtering,
        "4": example_4_analyze_results,
        "5": example_5_error_handling,
    }
    
    if args.example == "all":
        for name, func in examples.items():
            await func()
    else:
        await examples[args.example]()
    
    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n示例被用户中断")
    except Exception as e:
        print(f"\n示例运行失败: {e}")
        import traceback
        traceback.print_exc()

