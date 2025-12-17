#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量子位爬虫 - 快速启动脚本
无需复杂配置，一键运行爬取
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径，以便导入config
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))


def print_banner():
    """打印启动横幅"""
    print("\n" + "=" * 70)
    print("🚀 量子位(QbitAI)爬虫 - 快速启动")
    print("=" * 70)
    print("📍 网址: https://www.qbitai.com/")
    print("📝 功能: 爬取近两周内的所有文章和评论")
    print("💾 数据存储: MySQL数据库")
    print("=" * 70 + "\n")


def check_environment():
    """检查环境配置"""
    print("🔍 检查环境配置...\n")
    
    # (import_name, package_name, description)
    requirements = [
        ('httpx', 'httpx', 'HTTP请求库'),
        ('bs4', 'beautifulsoup4', 'HTML解析库'),
        ('sqlalchemy', 'sqlalchemy', 'ORM框架'),
        ('loguru', 'loguru', '日志库'),
        ('pymysql', 'pymysql', 'MySQL驱动'),
    ]
    
    missing = []
    for import_name, package_name, description in requirements:
        try:
            __import__(import_name)
            print(f"✅ {package_name:20} - {description}")
        except ImportError:
            print(f"❌ {package_name:20} - {description} (未安装)")
            missing.append(package_name)
    
    if missing:
        print(f"\n⚠️  发现缺失依赖: {', '.join(missing)}")
        print("请运行以下命令安装:")
        print(f"  pip install {' '.join(missing)}")
        print("\n或完整安装所有依赖:")
        print("  pip install -r requirements.txt")
        return False
    
    print("\n✅ 所有依赖检查完成\n")
    return True


def check_database_config():
    """检查数据库配置"""
    print("🗄️  检查数据库配置...\n")
    
    try:
        from config import settings
        from sqlalchemy import create_engine, text
        
        print(f"数据库配置:")
        print(f"  主机: {settings.DB_HOST}")
        print(f"  端口: {settings.DB_PORT}")
        print(f"  用户: {settings.DB_USER}")
        print(f"  数据库: {settings.DB_NAME}")
        print(f"  类型: {settings.DB_DIALECT}")
        
        # 尝试连接
        print("\n  尝试连接数据库...")
        
        # 构建连接字符串
        if settings.DB_DIALECT.lower() in ['postgresql', 'postgres']:
            db_url = f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        else:
            db_url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("  ✅ 数据库连接成功")
            return True
        except Exception as e:
            print(f"  ❌ 数据库连接失败: {e}")
            print("\n  请检查以下事项:")
            print("    1. 数据库服务是否运行")
            print("    2. 数据库用户名和密码是否正确")
            print("    3. 数据库是否存在")
            print("    4. .env文件配置是否正确")
            return False
    except ImportError:
        print("❌ 无法导入config模块或sqlalchemy")
        return False


def check_database_tables():
    """检查数据库表是否存在"""
    print("\n📋 检查数据库表...\n")
    
    try:
        from config import settings
        from sqlalchemy import create_engine, inspect
        
        # 构建连接字符串
        if settings.DB_DIALECT.lower() in ['postgresql', 'postgres']:
            db_url = f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        else:
            db_url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        
        engine = create_engine(db_url)
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # 检查表是否存在
        tables = ['qbitai_article', 'qbitai_article_comment']
        all_exist = True
        
        for table in tables:
            if table in existing_tables:
                print(f"  ✅ {table} - 表已存在")
            else:
                print(f"  ❌ {table} - 表不存在")
                all_exist = False
        
        if not all_exist:
            print("\n⚠️  发现缺失的表。")
            return False
        
        print("\n✅ 所有表都存在")
        return True
    except Exception as e:
        print(f"❌ 检查表时出错: {e}")
        return False


async def run_crawler():
    """运行爬虫"""
    print("\n" + "=" * 70)
    print("▶️  开始爬虫任务")
    print("=" * 70 + "\n")
    
    try:
        # 导入爬虫脚本
        sys.path.insert(0, str(Path(__file__).parent))
        from qbitai_scraper import main
        
        # 运行爬虫
        articles, comments = await main()
        
        print("\n" + "=" * 70)
        print("✅ 爬虫任务完成!")
        print("=" * 70)
        print(f"📊 爬取统计:")
        print(f"   📄 文章总数: {articles}")
        print(f"   💬 评论总数: {comments}")
        print(f"💾 数据已保存到数据库")
        print("=" * 70 + "\n")
        
        return True
    except Exception as e:
        print(f"\n❌ 爬虫执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主程序"""
    print_banner()
    
    # 检查环境
    if not check_environment():
        print("❌ 环境检查失败，请安装缺失的依赖")
        sys.exit(1)
    
    # 检查数据库配置
    if not check_database_config():
        print("❌ 数据库配置有问题，请修复")
        sys.exit(1)
    
    # 检查数据库表
    if not check_database_tables():
        print("⚠️  请先创建数据库表")
        response = input("\n是否现在创建表? (y/n) [默认: n]: ").strip().lower()
        if response == 'y':
            try:
                from config import settings
                from sqlalchemy import create_engine
                
                # 构建连接字符串
                if settings.DB_DIALECT.lower() in ['postgresql', 'postgres']:
                    db_url = f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
                else:
                    db_url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
                
                print(f"正在连接数据库并创建表...")
                
                # 导入模型
                # 确保 MediaCrawler 在路径中
                media_crawler_path = Path(__file__).parent / "MediaCrawler"
                if str(media_crawler_path) not in sys.path:
                    sys.path.append(str(media_crawler_path))
                
                from database.models import Base, QbitaiArticle, QbitaiArticleComment
                
                engine = create_engine(db_url)
                
                # 创建表
                # 只创建相关的表，或者创建所有表
                # Base.metadata.create_all(engine) 会创建所有继承自 Base 的表
                # 为了避免影响其他表，我们可以只创建我们需要的表，但通常 create_all 会检查表是否存在
                Base.metadata.create_all(engine)
                
                print("✅ 数据库表创建成功")
                
            except Exception as e:
                print(f"❌ 创建表失败: {e}")
                sys.exit(1)
        else:
            print("⚠️  请先创建数据库表，然后再运行爬虫")
            sys.exit(1)
    
    # 开始爬取
    success = asyncio.run(run_crawler())
    
    if success:
        print("\n🎉 全部完成！")
        print("\n💡 下次运行可以直接执行:")
        print("   python run_qbitai_crawler.py")
        sys.exit(0)
    else:
        print("\n❌ 爬虫执行失败，请查看上面的错误信息")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断爬虫")
        sys.exit(0)
