"""
策略复盘 "时光机" 脚本 (V1.0)
===================================
本脚本允许您回到任何一个历史时间点，使用当前的V2.1策略，
复盘并分析当时的市场环境，以审查和验证策略决策。

如何使用:
在终端中运行 (确保已激活conda环境):
python tests/replay_strategy_at_time.py [交易对] "[时间]"

示例:
python tests/replay_strategy_at_time.py BTCUSDT "2025-06-18 10:17:02"
"""
import asyncio
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from pprint import pprint
import argparse

# --- 准备测试环境 ---
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from config.config import config
from core.data_fetcher import DataFetcher
from core.indicator_calculator import IndicatorCalculator
from core.strategy_analyzer import StrategyAnalyzerV2

# --- 核心复盘逻辑 ---
async def fetch_replay_data(fetcher: DataFetcher, symbol: str, end_dt: datetime) -> dict:
    """获取复盘所需的、所有时间框架的历史数据"""
    tasks = [fetcher.fetch_historical_klines(symbol, tf, end_dt) for tf in config.TIMEFRAMES]
    results = await asyncio.gather(*tasks)
    
    data_dict = {}
    for tf, df in zip(config.TIMEFRAMES, results):
        if df is None or df.empty:
            print(f"❌ 错误: 无法获取 {symbol} 在 {tf} 的历史数据，复盘中止。")
            return {}
        data_dict[tf] = df
        
    return data_dict

def print_decision_breakdown(result: dict, analyzer: StrategyAnalyzerV2):
    """详细打印决策的拆解过程，并增加V2.2的诊断信息"""
    print("\n[STEP 5] 决策逻辑拆解:")
    
    trend = result['details']['2h_trend']
    trend_details = result['details']['trend_details']
    print(f"\n  - 2H趋势判断: {trend}")

    if trend == "RANGING":
        print(f"    - 原因: {trend_details.get('error', '未知震荡原因')}")
        return

    print(f"    - 条件检查: 价格({trend_details.get('price', 'N/A'):.4f}) < EMA10({trend_details.get('ema_fast', 'N/A'):.4f}) < EMA20({trend_details.get('ema_slow', 'N/A'):.4f})?")
    print(f"    - 斜率检查: EMA10斜率({trend_details.get('ema_fast_slope', 'N/A'):.4f}) < 0?")

    # --- V2.2 诊断模块 ---
    def print_frontier_diagnostics(frontier_type: str):
        details = result['details']
        if frontier_type == 'resistance':
            level_list = analyzer._identify_effective_resistance.original_resistances
            key_name = 'effective_resistance_name'
        else:
            level_list = analyzer._identify_effective_support.original_supports
            key_name = 'effective_support_name'
        
        print(f"\n  - [V2.2] {frontier_type.capitalize()} 前沿诊断:")
        if not level_list:
            print("    - 未找到有效的候选位。")
            return
            
        for i in range(len(level_list) - 1):
            current_name, current_level = level_list[i]
            next_name, next_level = level_list[i+1]
            distance = abs(next_level - current_level) / details.get('current_price', 1)
            is_clustered = distance < analyzer.params.CLUSTER_THRESHOLD

            print(f"    - 正在检查: {current_name} ({current_level:.4f}) vs {next_name} ({next_level:.4f})")
            print(f"      - 距离: {distance:.4%}, 阈值: {analyzer.params.CLUSTER_THRESHOLD:.2%}")
            if is_clustered:
                print(f"      - 结论: 距离过近，形成聚集区。考察对象升级至 {next_name}。")
            else:
                print(f"      - 结论: 距离足够远，{current_name} 是一个独立防线。")
                break # 找到了独立防线，后续无需再检查
        print(f"  - 最终有效前沿: {details.get(key_name, 'N/A')}")
    # --- 结束诊断模块 ---

    if 'effective_resistance_name' in result['details']:
        print_frontier_diagnostics('resistance')
    elif 'effective_support_name' in result['details']:
        print_frontier_diagnostics('support')

    if 'effective_resistance_name' in result['details']:
        resistance_name = result['details']['effective_resistance_name']
        resistance_level = result['details']['effective_resistance_level']
        print(f"\n  - 有效阻力位判断: {resistance_name} at {resistance_level:.4f}")
        
        price = result['details']['current_price']
        is_near = result['details']['is_near_resistance']
        proximity = abs(price - resistance_level) / price
        print(f"\n  - 价格接近判断: {is_near}")
        print(f"    - 价格({price:.4f}) 距离阻力位百分比: {proximity:.4%}")

        print(f"\n  - {config.SIGNAL_TIMEFRAME} 扳机信号判断: '{result.get('reason', '').split(' trigger: ')[-1]}'")
        print(f"    - 触发信号时间: {result['details'].get('trigger_candle_time', 'N/A')}")
    # 可以根据需要添加做多逻辑的打印
    
async def run_replay(symbol: str, timestamp_str: str):
    """执行完整的复盘流程"""
    print("="*50)
    print(f" 策略复盘: {symbol} at {timestamp_str}")
    print("="*50)
    
    try:
        target_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        print("❌ 错误: 时间格式不正确，请使用 'YYYY-MM-DD HH:MM:SS' 格式。")
        return

    # 1. 初始化所有模块
    fetcher = DataFetcher()
    await fetcher.initialize()
    calculator = IndicatorCalculator()
    analyzer = StrategyAnalyzerV2()
    
    # 2. 获取并处理数据
    print(f"\n[STEP 1] 正在获取截至 {timestamp_str} 的历史数据...")
    raw_data = await fetch_replay_data(fetcher, symbol, target_dt)
    if not raw_data: return
    
    print("\n[STEP 2] 正在为历史数据计算技术指标...")
    processed_data = calculator.calculate_indicators_for_all_timeframes(raw_data)
    if not processed_data:
        print("❌ 错误: 指标计算失败，复盘中止。")
        await fetcher.close()
        return

    # 3. 执行分析
    print("\n[STEP 3] 正在使用历史快照数据调用策略分析器...")
    result = analyzer.analyze(symbol, processed_data)
    
    # 4. 打印完整决策结果
    print("\n[STEP 4] 策略分析器返回的完整决策:")
    pprint(result)
    
    # 5. 拆解决策过程
    print_decision_breakdown(result, analyzer)

    print("\n" + "="*50)
    print(" 复盘完成")
    print("="*50)

    await fetcher.close()

# --- 临时修改策略分析器以暴露中间数据，仅为测试目的 ---
# 这是一种常见的调试技巧，称为"猴子补丁"
_original_identify_resistance = StrategyAnalyzerV2._identify_effective_resistance
def patched_identify_resistance(self, data_dict):
    res = _original_identify_resistance(self, data_dict)
    # 将中间计算结果附加到函数对象上，以便在测试脚本中访问
    patched_identify_resistance.original_resistances = [
        ('15m_EMA10', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
        ('15m_EMA20', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
        ('30m_EMA10', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
        ('30m_EMA20', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
    ]
    return res

_original_identify_support = StrategyAnalyzerV2._identify_effective_support
def patched_identify_support(self, data_dict):
    res = _original_identify_support(self, data_dict)
    patched_identify_support.original_supports = [
        ('30m_EMA20', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
        ('30m_EMA10', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
        ('15m_EMA20', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
        ('15m_EMA10', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
    ]
    return res

StrategyAnalyzerV2._identify_effective_resistance = patched_identify_resistance
StrategyAnalyzerV2._identify_effective_support = patched_identify_support
# -----------------------------------------------------------

# --- 脚本入口 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='策略复盘时光机')
    parser.add_argument('symbol', type=str, help='要复盘的交易对，例如 BTCUSDT')
    # 使用 nargs='+' 来捕获所有后续部分作为时间戳
    parser.add_argument('timestamp', nargs='+', help='要复盘的时间点，格式为 "YYYY-MM-DD HH:MM:SS"')
    
    args = parser.parse_args()
    
    # 将捕获到的时间戳部分用空格重新拼接成一个完整的字符串
    timestamp_str = " ".join(args.timestamp)
    
    asyncio.run(run_replay(args.symbol, timestamp_str)) 