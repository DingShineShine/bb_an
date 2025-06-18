"""
BinanceEventTrader - Strategy Analyzer (V2.1)
==============================================
首席系统架构师重构版

本模块实现了"顺大势，逆小势"的分层级多时间框架交易策略。
该策略基于严格的双向对称规则，分别处理上涨和下跌市场行情。

核心逻辑:
1.  **超大周期趋势过滤 (2H):** 确定主趋势方向（多头、空头、震荡）。
2.  **中大周期动态支撑/阻力识别 (15M & 30M):** 寻找回调/反弹的潜在"地板"或"天花板"。
3.  **小周期交易信号捕捉 (1M & 5M):** 在关键支撑/阻力位附近，寻找精准的、由成交量确认的入场时机。
"""

import pandas as pd
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from loguru import logger

from config.config import strategy_params, config

# V2.1: 参数已移至 config.py 的 StrategyParams，不再在此处定义

class StrategyAnalyzerV2:
    """
    策略分析器 V2.1
    实现了完整的、双向对称的交易规则。
    """

    def __init__(self):
        """初始化策略分析器"""
        self.params = strategy_params
        # 兼容旧版本config，如果不存在EMA_FAST等，则使用默认值
        if not hasattr(self.params, 'EMA_FAST'): self.params.EMA_FAST = 10
        if not hasattr(self.params, 'EMA_SLOW'): self.params.EMA_SLOW = 20
        logger.info("策略分析器 V2.1 初始化成功。")

    def analyze(self, symbol: str, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        主分析函数，根据提供的多时间框架数据生成交易决策。
        这是整个策略逻辑的入口点。

        Args:
            symbol (str): 交易对名称。
            data_dict (Dict[str, pd.DataFrame]): 包含多个时间框架数据的字典。
                需要键: '2h', '30m', '15m', '5m', '1m'。

        Returns:
            Dict[str, Any]: 包含交易决策和详细分析的字典。
        """
        try:
            # 步骤一：超大周期趋势过滤 (2H)
            trend, trend_details = self._determine_2h_trend(data_dict['2h'])

            decision = {
                'symbol': symbol,
                'decision': 'WAIT',
                'reason': '',
                'details': {
                    '2h_trend': trend,
                    'trend_details': trend_details
                },
                'timestamp': datetime.now()
            }

            if trend == "UPTREND":
                # 步骤二 (Part B): 执行上涨趋势的做多逻辑
                long_decision = self._analyze_long_opportunity(data_dict)
                # 智能合并，而不是覆盖 'details'
                decision['decision'] = long_decision.get('decision', 'WAIT')
                decision['reason'] = long_decision.get('reason', '')
                decision['details'].update(long_decision.get('details', {}))

            elif trend == "DOWNTREND":
                # 步骤二 (Part A): 执行下跌趋势的做空逻辑
                short_decision = self._analyze_short_opportunity(data_dict)
                # 智能合并，而不是覆盖 'details'
                decision['decision'] = short_decision.get('decision', 'WAIT')
                decision['reason'] = short_decision.get('reason', '')
                decision['details'].update(short_decision.get('details', {}))
            
            else: # RANGING
                # 步骤二 (Part C): 执行震荡市逻辑
                decision['reason'] = "2H trend is ranging. Standing by."

            logger.info(f"[{symbol}] 分析完成: {decision['decision']}. 原因: {decision['reason']}")
            return decision

        except KeyError as e:
            logger.error(f"[{symbol}] 分析失败: 缺少必要的时间框架数据 - {e}")
            return self._generate_error_decision(symbol, f"Missing data for timeframe: {e}")
        except Exception as e:
            logger.error(f"[{symbol}] 分析过程中发生未知错误: {e}", exc_info=True)
            return self._generate_error_decision(symbol, f"An unexpected error occurred: {e}")

    def _determine_2h_trend(self, df_2h: pd.DataFrame) -> Tuple[str, Dict]:
        """[核心] 规则 1: 判断2H图的严格趋势。"""
        if len(df_2h) < self.params.EMA_SLOW:
            return "RANGING", {"error": "Not enough 2h data"}

        latest = df_2h.iloc[-1]
        price = latest['close']
        ema_fast_val = latest[f'ema_{self.params.EMA_FAST}']
        ema_slow_val = latest[f'ema_{self.params.EMA_SLOW}']
        ema_fast_slope = latest['ema_fast_slope']
        
        details = {
            'price': price,
            'ema_fast': ema_fast_val,
            'ema_slow': ema_slow_val,
            'ema_fast_slope': ema_fast_slope,
        }

        # 严格多头排列定义
        is_uptrend = (price > ema_fast_val > ema_slow_val) and (ema_fast_slope > 0)
        if is_uptrend:
            return "UPTREND", details

        # 严格空头排列定义
        is_downtrend = (price < ema_fast_val < ema_slow_val) and (ema_fast_slope < 0)
        if is_downtrend:
            return "DOWNTREND", details

        return "RANGING", details
    
    # --- 做多逻辑 (Part B) ---
    def _analyze_long_opportunity(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """分析做多机会的完整流程。"""
        details = {}
        # 1. 识别动态支撑
        support_level, support_name = self._identify_effective_support(data_dict)
        details.update({'effective_support_name': support_name, 'effective_support_level': support_level})
        if not support_level:
            return {'decision': 'WAIT', 'reason': 'Could not identify effective support level.', 'details': details}

        # 2. 检查价格是否在支撑位附近
        signal_timeframe = config.SIGNAL_TIMEFRAME
        price = data_dict[signal_timeframe].iloc[-1]['close']
        is_near_support = abs(price - support_level) / price < self.params.PROXIMITY_THRESHOLD
        details.update({'current_price': price, 'is_near_support': is_near_support})

        if not is_near_support:
            return {'decision': 'WAIT', 'reason': f'Price not near effective support {support_name} ({support_level:.4f}).', 'details': details}

        # 3. 捕捉小周期做多信号
        trigger, trigger_details = self._find_long_trigger(data_dict[signal_timeframe])
        details.update(trigger_details)

        if trigger:
            return {
                'decision': 'LONG', 
                'reason': f'Price at support {support_name} with trigger: {trigger}', 
                'details': details
            }
        
        return {'decision': 'WAIT', 'reason': f'Price at support {support_name}, but no trigger signal found.', 'details': details}

    def _identify_effective_support(self, data_dict: Dict[str, pd.DataFrame]) -> Tuple[Optional[float], Optional[str]]:
        """[V2.2] 识别有效支撑前沿 (Effective Support Frontier)"""
        price = data_dict['1m'].iloc[-1]['close']
        # 支撑梯队，从强到弱排序
        support_levels = [
            ('30m_EMA20', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
            ('30m_EMA10', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
            ('15m_EMA20', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
            ('15m_EMA10', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
        ]

        # 找到所有在价格下方的支撑位
        valid_supports = [(name, level) for name, level in support_levels if price >= level]

        if not valid_supports:
            return None, None

        # 第一个候选者是离价格最近的（最强的）有效支撑
        effective_support = valid_supports[0]

        # [核心逻辑] 检查聚集区效应
        for i in range(len(valid_supports) - 1):
            current_name, current_level = valid_supports[i]
            next_name, next_level = valid_supports[i+1] # 更弱一级的支撑

            # 如果两个支撑位非常接近，则认为它们形成聚集区，应以更强的为准
            if abs(current_level - next_level) / price < self.params.CLUSTER_THRESHOLD:
                # 当前支撑位被聚集，继续使用更强的支撑位
                continue
            else:
                # 找到了一个独立的、非聚集的支撑位
                effective_support = valid_supports[i]
                break
        
        return effective_support[1], effective_support[0]

    def _find_long_trigger(self, df_5m: pd.DataFrame) -> Tuple[Optional[str], Dict]:
        """规则 3B: 在5M图上寻找"缩量企稳"或"放量反转"证据。"""
        avg_volume = df_5m['volume'].rolling(window=20).mean().iloc[-1]
        avg_body_size = abs(df_5m['close'] - df_5m['open']).rolling(window=20).mean().iloc[-1]
        
        # 检查最近3根K线
        for i in range(1, 4):
            if len(df_5m) < i + 1: continue
            candle = df_5m.iloc[-i]
            
            # --- 检查1: 缩量企稳 ---
            is_bearish = candle['close'] < candle['open']
            if is_bearish:
                is_volume_shrinking = candle['volume'] < avg_volume * self.params.VOLUME_SHRINK_FACTOR
                is_body_small = abs(candle['close'] - candle['open']) < avg_body_size
                if is_volume_shrinking and is_body_small:
                    return "Shrinking Volume Stability", {'trigger_candle_time': candle.name}

            # --- 检查2: 放量反转 ---
            if i > 1:
                prev_candle = df_5m.iloc[-i-1]
                is_bullish_engulfing = (candle['close'] > candle['open'] and 
                                        prev_candle['close'] < prev_candle['open'] and 
                                        candle['close'] > prev_candle['open'] and 
                                        candle['open'] < prev_candle['close'])
                if is_bullish_engulfing:
                    is_volume_spike = candle['volume'] > avg_volume * self.params.VOLUME_SPIKE_FACTOR
                    if is_volume_spike:
                        return "Volume Spike Reversal", {'trigger_candle_time': candle.name}
        
        return None, {}

    # --- 做空逻辑 (Part A) ---
    def _analyze_short_opportunity(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """分析做空机会的完整流程。"""
        details = {}
        # 1. 识别动态阻力
        resistance_level, resistance_name = self._identify_effective_resistance(data_dict)
        details.update({'effective_resistance_name': resistance_name, 'effective_resistance_level': resistance_level})
        if not resistance_level:
            return {'decision': 'WAIT', 'reason': 'Could not identify effective resistance level.', 'details': details}

        # 2. 检查价格是否在阻力位附近
        signal_timeframe = config.SIGNAL_TIMEFRAME
        price = data_dict[signal_timeframe].iloc[-1]['close']
        is_near_resistance = abs(price - resistance_level) / price < self.params.PROXIMITY_THRESHOLD
        details.update({'current_price': price, 'is_near_resistance': is_near_resistance})

        if not is_near_resistance:
            return {'decision': 'WAIT', 'reason': f'Price not near effective resistance {resistance_name} ({resistance_level:.4f}).', 'details': details}

        # 3. 捕捉小周期做空信号
        trigger, trigger_details = self._find_short_trigger(data_dict[signal_timeframe])
        details.update(trigger_details)

        if trigger:
            return {
                'decision': 'SHORT', 
                'reason': f'Price at resistance {resistance_name} with trigger: {trigger}', 
                'details': details
            }
        
        return {'decision': 'WAIT', 'reason': f'Price at resistance {resistance_name}, but no trigger signal found.', 'details': details}

    def _identify_effective_resistance(self, data_dict: Dict[str, pd.DataFrame]) -> Tuple[Optional[float], Optional[str]]:
        """[V2.2] 识别有效阻力前沿 (Effective Resistance Frontier)"""
        price = data_dict['1m'].iloc[-1]['close']
        # 阻力梯队，从弱到强排序
        resistance_levels = [
            ('15m_EMA10', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
            ('15m_EMA20', data_dict['15m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
            ('30m_EMA10', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_FAST}']),
            ('30m_EMA20', data_dict['30m'].iloc[-1][f'ema_{self.params.EMA_SLOW}']),
        ]

        # 找到所有在价格上方的阻力位
        valid_resistances = [(name, level) for name, level in resistance_levels if price <= level]

        if not valid_resistances:
            return None, None

        # 第一个候选者是离价格最近的（最弱的）有效阻力
        effective_resistance = valid_resistances[0]

        # [核心逻辑] 检查聚集区效应
        for i in range(len(valid_resistances) - 1):
            current_name, current_level = valid_resistances[i]
            next_name, next_level = valid_resistances[i+1] # 更强一级的阻力

            # 如果两个阻力位非常接近，则认为它们形成聚集区，应以更强的为准
            if abs(next_level - current_level) / price < self.params.CLUSTER_THRESHOLD:
                # 当前阻力位太弱且被聚集，升级到更强的阻力位
                effective_resistance = valid_resistances[i+1]
                continue
            else:
                # 找到了一个独立的、非聚集的阻力位
                effective_resistance = valid_resistances[i]
                break
        
        return effective_resistance[1], effective_resistance[0]

    def _find_short_trigger(self, df_5m: pd.DataFrame) -> Tuple[Optional[str], Dict]:
        """规则 3A: 在5M图上寻找"放量滞涨"证据。"""
        candle = df_5m.iloc[-1]
        avg_volume = df_5m['volume'].rolling(window=20).mean().iloc[-1]
        
        # 必须是阳线或十字星
        if candle['close'] >= candle['open']:
            is_volume_spike = candle['volume'] > avg_volume * self.params.VOLUME_SPIKE_FACTOR
            
            body_size = abs(candle['close'] - candle['open'])
            # 处理body_size为0的情况，避免除零错误
            if body_size > 1e-9: # 使用一个很小的值来避免浮点数精度问题
                upper_shadow = candle['high'] - max(candle['open'], candle['close'])
                is_stagnated = upper_shadow > body_size * self.params.UPPER_SHADOW_FACTOR
            else: # 十字星
                is_stagnated = (candle['high'] - candle['low']) > 0 # 确保不是一条横线
            
            if is_volume_spike and is_stagnated:
                return "Volume Spike Stagnation", {'trigger_candle_time': candle.name}

        return None, {}

    def _generate_error_decision(self, symbol: str, reason: str) -> Dict[str, Any]:
        """生成统一的错误决策格式"""
        return {
            'symbol': symbol,
            'decision': 'ERROR',
            'reason': reason,
            'details': {},
            'timestamp': datetime.now()
        }

# 创建全局策略分析器实例
strategy_analyzer_v2 = StrategyAnalyzerV2()

# 便捷函数，方便外部调用
def analyze_trading_opportunity_v2(symbol: str, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """便捷函数：分析交易机会 V2.1"""
    # 确保所有需要的数据都已计算指标
    # 注意：指标计算应在调用此函数之前完成
    return strategy_analyzer_v2.analyze(symbol, data_dict)

# 导出
__all__ = ['StrategyAnalyzerV2', 'strategy_analyzer_v2', 'analyze_trading_opportunity_v2'] 