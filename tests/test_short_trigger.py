"""
策略复盘与单元测试脚本
========================
场景: 复盘 BTCUSDT "放量滞涨" 做空信号

本测试旨在精确模拟一个市场环境，该环境将触发 V2.1 策略中的
"下跌趋势做空逻辑"，并由"放量滞涨"信号作为最终的扳机。
"""
import sys
import pandas as pd
from pathlib import Path
from pprint import pprint

# --- 准备测试环境 ---
# 将项目根目录添加到Python路径，以便能够导入我们的模块
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from config.config import config
from core.strategy_analyzer import StrategyAnalyzerV2

# --- 模拟市场数据 ---
def create_mock_data() -> dict:
    """
    创建一个精确的数据场景，用于触发做空信号。
    """
    # 场景设定:
    # 1. 2H 趋势: 严格空头排列
    # 2. 阻力位: 价格反弹至 15m_EMA10 附近
    # 3. 触发信号 (1m): 出现一根成交量放大、且带有长上影线的K线

    # --- 1. 2H 数据 (趋势过滤) ---
    # 扩展数据以满足指标计算的最小长度要求 (>=20)
    opens_2h = [50500, 50300, 50100] * 7
    highs_2h = [50600, 50400, 50200] * 7
    lows_2h = [50200, 50000, 49800] * 7
    closes_2h = [50300, 50100, 49900] * 7
    volumes_2h = [1000, 1100, 1200] * 7
    ema_10_2h = [50150, 50050, 49950] * 7
    ema_20_2h = [50350, 50250, 50150] * 7
    slope_2h = [-100, -100, -100] * 7

    df_2h = pd.DataFrame({
        'open': opens_2h,
        'high': highs_2h,
        'low': lows_2h,
        'close': closes_2h,
        'volume': volumes_2h,
        # 手动设置指标以满足"严格空头排列"
        'ema_10': ema_10_2h,
        'ema_20': ema_20_2h,
        'ema_fast_slope': slope_2h
    })

    # --- 2. 15m & 30m 数据 (寻找阻力位) ---
    # 设定 15m_EMA10 为有效阻力位
    resistance_level = 50010.5
    df_15m = pd.DataFrame({
        'ema_10': [resistance_level],
        'ema_20': [resistance_level + 50]
    })
    df_30m = pd.DataFrame({
        'ema_10': [resistance_level + 100],
        'ema_20': [resistance_level + 150]
    })
    
    # --- 3. 1m 数据 (信号捕捉) ---
    # 创造一个21周期的DataFrame，最后一根K线是触发信号
    base_volume = 100
    volumes = [base_volume] * 20 + [base_volume * 2.1] # 最后一根成交量放大
    
    # 构造K线，最后一根是"放量滞涨"形态
    # 实体很小，但上影线很长
    opens = [50000] * 20 + [50005]
    closes = [50001] * 20 + [50006] # 阳线
    highs = [50002] * 20 + [50010]  # body=1, upper_shadow=4, 满足滞涨
    lows = [49999] * 20 + [50004]

    df_1m = pd.DataFrame({
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes,
    })
    # 计算测试需要用的成交量均线
    df_1m['volume_MA_20'] = df_1m['volume'].rolling(window=20).mean()

    # --- 4. 5m 数据 (占位) ---
    df_5m = pd.DataFrame({'close': [50000]}) # 内容不重要，但必须存在

    return {
        '2h': df_2h, '30m': df_30m, '15m': df_15m, '5m': df_5m, '1m': df_1m
    }

# --- 执行测试 ---
def run_test():
    """运行复盘测试并打印结果"""
    print("="*50)
    print(" 复盘测试: BTCUSDT '放量滞涨' 做空信号")
    print("="*50)
    
    # 1. 准备数据和分析器
    mock_data_dict = create_mock_data()
    analyzer = StrategyAnalyzerV2()
    
    # 修改配置，确保信号周期为1m
    config.SIGNAL_TIMEFRAME = '1m'
    
    # 2. 执行分析
    print("\n[STEP 1] 正在使用模拟数据调用策略分析器...")
    result = analyzer.analyze("BTCUSDT", mock_data_dict)
    
    # 3. 打印完整决策结果
    print("\n[STEP 2] 策略分析器返回的完整决策:")
    pprint(result)
    
    # 4. 拆解决策过程
    print("\n[STEP 3] 决策逻辑拆解:")
    
    # 趋势判断
    trend = result['details']['2h_trend']
    trend_details = result['details']['trend_details']
    print(f"\n  - 2H趋势判断: {trend}")

    # 增加对震荡市的处理，防止因数据不足导致的测试崩溃
    if trend == "RANGING":
        print(f"    - 原因: {trend_details.get('error', '未知震荡原因')}")
        print("\n" + "="*50)
        print(" 复盘终止：2H趋势不满足交易条件。")
        print("="*50)
        return

    print(f"    - 条件检查: 价格({trend_details['price']}) < EMA10({trend_details['ema_fast']}) < EMA20({trend_details['ema_slow']})?")
    print(f"    - 结果: {trend_details['price'] < trend_details['ema_fast'] < trend_details['ema_slow']}")
    print(f"    - 斜率检查: EMA10斜率({trend_details['ema_fast_slope']}) < 0?")
    print(f"    - 结果: {trend_details['ema_fast_slope'] < 0}")

    # 阻力判断
    resistance_name = result['details']['effective_resistance_name']
    resistance_level = result['details']['effective_resistance_level']
    print(f"\n  - 有效阻力位判断: {resistance_name} at {resistance_level:.4f}")
    
    # 价格接近判断
    price = result['details']['current_price']
    is_near = result['details']['is_near_resistance']
    proximity = abs(price - resistance_level) / price
    print(f"\n  - 价格接近判断: {is_near}")
    print(f"    - 价格({price:.4f}) 距离阻力位百分比: {proximity:.4%}")
    print(f"    - 是否小于阈值({analyzer.params.PROXIMITY_THRESHOLD:.2%})? {proximity < analyzer.params.PROXIMITY_THRESHOLD}")

    # 信号触发判断
    print(f"\n  - 1M扳机信号判断: '放量滞涨'")
    last_candle = mock_data_dict['1m'].iloc[-1]
    avg_volume = mock_data_dict['1m']['volume_MA_20'].iloc[-1]
    
    # 打印触发信号时的快照
    print(f"\n    - 触发信号时间: {result['details'].get('trigger_candle_time', 'N/A')}")
    print(f"    - 触发K线 (OHLC): O:{last_candle['open']} H:{last_candle['high']} L:{last_candle['low']} C:{last_candle['close']}")

    # 放量检查
    is_volume_spike = last_candle['volume'] > avg_volume * analyzer.params.VOLUME_SPIKE_FACTOR
    print(f"\n    - 放量检查: {is_volume_spike}")
    print(f"      - 当前成交量: {last_candle['volume']}")
    print(f"      - 20周期均量: {avg_volume:.2f}")
    print(f"      - 是否 > {avg_volume:.2f} * {analyzer.params.VOLUME_SPIKE_FACTOR}? {is_volume_spike}")

    # 滞涨检查 (长上影线)
    body_size = abs(last_candle['close'] - last_candle['open'])
    upper_shadow = last_candle['high'] - max(last_candle['open'], last_candle['close'])
    is_stagnated = upper_shadow > body_size * analyzer.params.UPPER_SHADOW_FACTOR
    print(f"\n    - 滞涨检查 (长上影线): {is_stagnated}")
    print(f"      - K线实体大小: {body_size:.2f}")
    print(f"      - 上影线长度: {upper_shadow:.2f}")
    print(f"      - 是否 > {body_size:.2f} * {analyzer.params.UPPER_SHADOW_FACTOR}? {is_stagnated}")
    
    print("\n" + "="*50)
    print(" 复盘完成")
    print("="*50)

if __name__ == "__main__":
    run_test() 