#!/usr/bin/env python3
"""
BinanceEventTrader 启动脚本
提供用户友好的程序启动和环境检查功能
"""
import os
import sys
import subprocess
from pathlib import Path


def print_banner():
    """显示程序启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🚀 BinanceEventTrader 币安事件合约交易机器人 🚀        ║
║                                                              ║
║                    策略：顺大势，逆小势                        ║
║                多时间框架RSI背离自动化交易                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_python_version():
    """检查Python版本"""
    print("🔍 检查Python版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        print(f"   当前版本: Python {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python版本检查通过: {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """检查依赖包是否安装"""
    print("\n🔍 检查依赖包...")
    
    try:
        import pandas
        import numpy
        import aiohttp
        import websockets
        import loguru
        from binance.client import Client
        print("✅ 核心依赖包检查通过")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return False


def check_config_file():
    """检查配置文件"""
    print("\n🔍 检查配置文件...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists():
        if env_example.exists():
            print("⚠️  未发现 .env 文件")
            print("请根据以下步骤配置:")
            print("1. 复制 .env.example 为 .env")
            print("2. 编辑 .env 文件，填入您的API密钥")
            print("3. 建议先使用测试网进行测试")
            return False
        else:
            print("❌ 配置文件缺失")
            return False
    
    print("✅ 配置文件检查通过")
    return True


def create_directories():
    """创建必要的目录"""
    print("\n🔍 创建必要目录...")
    
    directories = ["logs", "config", "core"]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ 目录创建完成")


def display_config_info():
    """显示配置信息"""
    print("\n📋 配置信息:")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        use_testnet = os.getenv('USE_TESTNET', 'true').lower() == 'true'
        api_key = os.getenv('BINANCE_TESTNET_API_KEY' if use_testnet else 'BINANCE_API_KEY')
        
        print(f"   交易模式: {'测试网' if use_testnet else '主网'}")
        print(f"   API密钥: {'已配置' if api_key else '未配置'}")
        
        if not api_key:
            print("⚠️  请确保已正确配置API密钥")
            
    except Exception as e:
        print(f"⚠️  无法读取配置: {e}")


def run_main_program():
    """封装启动主程序的逻辑"""
    print("\n🚀 正在启动主程序...\n")
    try:
        # 使用 subprocess 启动主程序
        # 这使得主程序在一个独立的进程中运行，与启动脚本分离
        subprocess.run(["python", "main.py"], check=True)
        print("\n✅ 主程序运行结束。")
    except FileNotFoundError:
        print("\n❌ 错误: main.py 文件未找到！请确保主程序文件存在。")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 主程序运行时发生错误: {e}")
    except Exception as e:
        print(f"\n❌ 启动过程中发生未知错误: {e}")


def main():
    """主函数"""
    print_banner()
    
    print("正在进行启动前检查...\n")
    
    # 检查Python版本
    if not check_python_version():
        input("\n按回车键退出...")
        sys.exit(1)
    
    # 检查依赖包
    if not check_dependencies():
        print("\n安装依赖包:")
        print("pip install -r requirements.txt")
        input("\n按回车键退出...")
        sys.exit(1)
    
    # 检查配置文件
    if not check_config_file():
        input("\n按回车键退出...")
        sys.exit(1)
    
    # 创建目录
    create_directories()
    
    # 显示配置信息
    display_config_info()
    
    print("\n" + "="*60)
    print("🎯 所有检查通过！准备启动交易机器人...")
    print("="*60)
    
    # 检查是否在Docker等非交互式环境中运行
    if os.environ.get('EXECUTION_MODE') == 'docker':
        print("\n[INFO] 检测到Docker环境，将自动启动主程序...")
        run_main_program()
    else:
        # 在本地交互式环境中运行
        print("\n📢 使用提示:")
        print("• 当前版本仅进行市场分析，不执行实际交易")
        print("• 建议先在测试网环境下观察程序运行")
        print("• 程序运行时会生成详细的分析日志")
        print("• 按 Ctrl+C 可以安全停止程序")

        while True:
            choice = input("\n是否现在启动程序？\n1. 是，立即启动\n2. 否，退出\n\n请选择 (1/2): ").strip()
            if choice == '1':
                run_main_program()
                break
            elif choice == '2':
                print("程序已退出。")
                break
            else:
                print("无效输入，请输入 1 或 2。")
        
        input("\n按回车键退出...")


if __name__ == "__main__":
    try:
        main()
    except EOFError:
        # 这个捕获现在主要用于处理一些未预料到的非交互式执行情况
        print("\n[ERROR] 启动过程中检测到EOF错误。")
        print("如果是通过Docker运行，请确保 'EXECUTION_MODE=docker' 环境变量已在docker-compose.yml中设置。")
    except KeyboardInterrupt:
        print("\n\n操作被用户中断。程序已退出。") 