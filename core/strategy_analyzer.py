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

            else:  # RANGING
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
        support_name, support_level = self._identify_effective_support(data_dict)
        details.update({'effective_support_name': support_name, 'effective_support_level': support_level})
        if not support_level:
            return {'decision': 'WAIT', 'reason': 'Could not identify effective support level.', 'details': details}

        # 2. 检查价格是否在支撑位附近
        signal_timeframe = config.SIGNAL_TIMEFRAME
        price = data_dict[signal_timeframe].iloc[-1]['close']
        is_near_support = abs(price - support_level) / price < self.params.PROXIMITY_THRESHOLD
        details.update({'current_price': price, 'is_near_support': is_near_support})

        if not is_near_support:
            return {'decision': 'WAIT',
                    'reason': f'Price not near effective support {support_name} ({support_level:.4f}).',
                    'details': details}

        # 3. 捕捉小周期做多信号
        trigger, trigger_details = self._find_long_trigger(data_dict[signal_timeframe])
        details.update(trigger_details)

        if trigger:
            # --- V2.5 新增: 构建详细的决策快照 ---
            reason = f"Price at support {support_name}. Trigger: {trigger}."
            if trigger == "Hammer Pattern":
                reason += f" (LS({trigger_details.get('lower_shadow', 0):.2f}) > Body({trigger_details.get('body_size', 0):.2f}) * {trigger_details.get('shadow_factor_used', 0):.1f})"
            elif trigger == "Bullish Volume-Price Divergence":
                reason += f" (Body/Range({trigger_details.get('body_to_range_ratio', 0):.1%}) < {trigger_details.get('threshold_pct_used', 0):.1%})"

            return {
                'decision': 'LONG',
                'reason': reason,
                'details': details
            }

        return {'decision': 'WAIT', 'reason': f'Price at support {support_name}, but no trigger signal found.',
                'details': details}

    def _identify_effective_support(self, data_dict: Dict[str, pd.DataFrame]) -> Tuple[Optional[str], Optional[float]]:
        """
        V2.4 区间攻防算法：识别有效支撑 (2H趋势向上时)
        """
        strat_params = self.params
        candle = data_dict[config.SIGNAL_TIMEFRAME].iloc[-1]
        open_price, close_price = candle['open'], candle['close']

        support_levels = {
            f"{config.SIGNAL_TIMEFRAME}_EMA{strat_params.EMA_FAST}": data_dict[config.SIGNAL_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_FAST}'],
            f"{config.SIGNAL_TIMEFRAME}_EMA{strat_params.EMA_SLOW}": data_dict[config.SIGNAL_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_SLOW}'],
            f"{config.TREND_TIMEFRAME}_EMA{strat_params.EMA_FAST}": data_dict[config.TREND_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_FAST}'],
            f"{config.TREND_TIMEFRAME}_EMA{strat_params.EMA_SLOW}": data_dict[config.TREND_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_SLOW}'],
        }
        # 按价格从高到低排序
        levels = sorted(support_levels.items(), key=lambda item: item[1], reverse=True)
        (s1_n, s1_v), (s2_n, s2_v), (s3_n, s3_v), (s4_n, s4_v) = levels[0], levels[1], levels[2], levels[3]

        def get_zone(price):
            if price > s1_v: return 0
            if s2_v < price <= s1_v: return 1
            if s3_v < price <= s2_v: return 2
            if s4_v < price <= s3_v: return 3
            return 4 # price <= s4_v
            
        open_zone, close_zone = get_zone(open_price), get_zone(close_price)

        # 规则1: 开盘和收盘在同一区间
        if open_zone == close_zone:
            if open_zone == 0: return s1_n, s1_v
            if open_zone == 1: return s2_n, s2_v
            if open_zone == 2: return s3_n, s3_v
            if open_zone == 3: return s4_n, s4_v
            if open_zone == 4: return None, None # 回调过深，无有效支撑

        # 规则2: 开盘和收盘跨越了边界线
        if close_price < open_price: # 阴线，空头向下突破
            if close_zone == 1: return s2_n, s2_v
            if close_zone == 2: return s3_n, s3_v
            if close_zone == 3: return s4_n, s4_v
            if close_zone == 4: return None, None
        else: # 阳线，多头向上反弹
            if open_zone == 1: return s1_n, s1_v # 从zone1弹起，说明s1是支撑
            if open_zone == 2: return s2_n, s2_v
            if open_zone == 3: return s3_n, s3_v
            if open_zone == 4: return s4_n, s4_v
            
        return None, None

    def _find_long_trigger(self, df_5m: pd.DataFrame) -> Tuple[Optional[str], Dict]:
        """
        规则 3B (V2.3): 在5M图上寻找多种"放量企稳"的复合证据。
        - 形态1: 看涨锤子线 (Hammer)
        - 形态2: 看涨量价背离 (Volume-Price Divergence)
        """
        params = self.params
        if len(df_5m) < params.TRIGGER_VOLUME_AVG_PERIOD + 2:
            return None, {}

        candle = df_5m.iloc[-1]
        prev_candle = df_5m.iloc[-2]

        # 1. 检查成交量是否放大 (逻辑与做空相同)
        avg_volume = df_5m['volume'].rolling(window=params.TRIGGER_VOLUME_AVG_PERIOD).mean().iloc[-2]
        is_volume_spike = (candle['volume'] > avg_volume * params.TRIGGER_VOLUME_SPIKE_FACTOR) or \
                          (candle['volume'] > prev_candle['volume'] * params.TRIGGER_VOLUME_SPIKE_FACTOR)

        if not is_volume_spike:
            return None, {}

        # 2. 分析K线形态和构建详细信息
        body_size = abs(candle['close'] - candle['open'])
        upper_shadow = candle['high'] - max(candle['open'], candle['close'])
        lower_shadow = min(candle['open'], candle['close']) - candle['low']
        candle_range = candle['high'] - candle['low']

        details = {
            'volume': candle['volume'],
            'avg_volume': avg_volume,
            'is_volume_spike': is_volume_spike,
            'trigger_candle_time': candle.name,
        }

        # 形态一: 锤子线 (长下影, 不关心颜色)
        # 条件: 下影线是实体的N倍, 且下影线也是上影线的N倍
        if body_size > 1e-9 and \
                lower_shadow > body_size * params.TRIGGER_SHADOW_FACTOR and \
                lower_shadow > upper_shadow * params.TRIGGER_SHADOW_FACTOR:
            details.update({
                'pattern': 'Hammer',
                'lower_shadow': lower_shadow,
                'body_size': body_size,
                'upper_shadow': upper_shadow,
                'shadow_factor_used': params.TRIGGER_SHADOW_FACTOR,
            })
            return "Hammer Pattern", details

        # 形态二: 量价背离 (放量收小阴线实体)
        # 条件: 实体很小(相对于总振幅), 且是阴线(代表抛售努力)
        if candle_range > 1e-9 and \
                (body_size / candle_range) < params.TRIGGER_SMALL_BODY_THRESHOLD_PCT and \
                candle['close'] < candle['open']:
            details.update({
                'pattern': 'Bullish Divergence',
                'body_size': body_size,
                'candle_range': candle_range,
                'body_to_range_ratio': body_size / candle_range,
                'threshold_pct_used': params.TRIGGER_SMALL_BODY_THRESHOLD_PCT,
            })
            return "Bullish Volume-Price Divergence", details

        return None, {}

    # --- 做空逻辑 (Part A) ---
    def _analyze_short_opportunity(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """分析做空机会的完整流程。"""
        details = {}
        # 1. 识别动态阻力
        resistance_name, resistance_level = self._identify_effective_resistance(data_dict)
        details.update({'effective_resistance_name': resistance_name, 'effective_resistance_level': resistance_level})
        if not resistance_level:
            return {'decision': 'WAIT', 'reason': 'Could not identify effective resistance level.', 'details': details}

        # 2. 检查价格是否在阻力位附近
        signal_timeframe = config.SIGNAL_TIMEFRAME
        price = data_dict[signal_timeframe].iloc[-1]['close']
        is_near_resistance = abs(price - resistance_level) / price < self.params.PROXIMITY_THRESHOLD
        details.update({'current_price': price, 'is_near_resistance': is_near_resistance})

        if not is_near_resistance:
            return {'decision': 'WAIT',
                    'reason': f'Price not near effective resistance {resistance_name} ({resistance_level:.4f}).',
                    'details': details}

        # 3. 捕捉小周期做空信号
        trigger, trigger_details = self._find_short_trigger(data_dict[signal_timeframe])
        details.update(trigger_details)

        if trigger:
            # --- V2.5 新增: 构建详细的决策快照 ---
            reason = f"Price at resistance {resistance_name}. Trigger: {trigger}."
            if trigger == "Shooting Star Pattern":
                reason += f" (US({trigger_details.get('upper_shadow', 0):.2f}) > Body({trigger_details.get('body_size', 0):.2f}) * {trigger_details.get('shadow_factor_used', 0):.1f})"
            elif trigger == "Bearish Volume-Price Divergence":
                reason += f" (Body/Range({trigger_details.get('body_to_range_ratio', 0):.1%}) < {trigger_details.get('threshold_pct_used', 0):.1%})"
            
            return {
                'decision': 'SHORT',
                'reason': reason,
                'details': details
            }

        return {'decision': 'WAIT', 'reason': f'Price at resistance {resistance_name}, but no trigger signal found.',
                'details': details}

    def _identify_effective_resistance(self, data_dict: Dict[str, pd.DataFrame]) -> Tuple[Optional[str], Optional[float]]:
        """
        V2.4 区间攻防算法：识别有效阻力 (2H趋势向下时)
        """
        strat_params = self.params
        candle = data_dict[config.SIGNAL_TIMEFRAME].iloc[-1]
        open_price, close_price = candle['open'], candle['close']

        resistance_levels = {
            f"{config.SIGNAL_TIMEFRAME}_EMA{strat_params.EMA_FAST}": data_dict[config.SIGNAL_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_FAST}'],
            f"{config.SIGNAL_TIMEFRAME}_EMA{strat_params.EMA_SLOW}": data_dict[config.SIGNAL_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_SLOW}'],
            f"{config.TREND_TIMEFRAME}_EMA{strat_params.EMA_FAST}": data_dict[config.TREND_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_FAST}'],
            f"{config.TREND_TIMEFRAME}_EMA{strat_params.EMA_SLOW}": data_dict[config.TREND_TIMEFRAME].iloc[-1][f'ema_{strat_params.EMA_SLOW}'],
        }
        # 按价格从低到高排序
        levels = sorted(resistance_levels.items(), key=lambda item: item[1])
        (r1_n, r1_v), (r2_n, r2_v), (r3_n, r3_v), (r4_n, r4_v) = levels[0], levels[1], levels[2], levels[3]

        def get_zone(price):
            if price < r1_v: return 0
            if r1_v <= price < r2_v: return 1
            if r2_v <= price < r3_v: return 2
            if r3_v <= price < r4_v: return 3
            return 4 # price >= r4_v

        open_zone, close_zone = get_zone(open_price), get_zone(close_price)

        # 规则1: 开盘和收盘在同一区间
        if open_zone == close_zone:
            if open_zone == 0: return r1_n, r1_v
            if open_zone == 1: return r2_n, r2_v
            if open_zone == 2: return r3_n, r3_v
            if open_zone == 3: return r4_n, r4_v
            if open_zone == 4: return None, None  # 反弹过强，无有效阻力

        # 规则2: 开盘和收盘跨越了边界线
        if close_price > open_price:  # 阳线，多头向上突破
            if close_zone == 1: return r2_n, r2_v
            if close_zone == 2: return r3_n, r3_v
            if close_zone == 3: return r4_n, r4_v
            if close_zone == 4: return None, None
        else:  # 阴线，空头向下打压
            if open_zone == 1: return r1_n, r1_v # 从zone1跌破，说明r1是阻力
            if open_zone == 2: return r2_n, r2_v
            if open_zone == 3: return r3_n, r3_v
            if open_zone == 4: return r4_n, r4_v
            
        return None, None

    def _find_short_trigger(self, df_5m: pd.DataFrame) -> Tuple[Optional[str], Dict]:
        """
        规则 3A (V2.3): 在5M图上寻找多种"放量滞涨"的复合证据。
        - 形态1: 看跌射击之星 (Shooting Star)
        - 形态2: 看跌量价背离 (Volume-Price Divergence)
        """
        params = self.params
        if len(df_5m) < params.TRIGGER_VOLUME_AVG_PERIOD + 2:
            return None, {}

        candle = df_5m.iloc[-1]
        prev_candle = df_5m.iloc[-2]

        # 1. 检查成交量是否放大
        avg_volume = df_5m['volume'].rolling(window=params.TRIGGER_VOLUME_AVG_PERIOD).mean().iloc[-2]
        is_volume_spike = (candle['volume'] > avg_volume * params.TRIGGER_VOLUME_SPIKE_FACTOR) or \
                          (candle['volume'] > prev_candle['volume'] * params.TRIGGER_VOLUME_SPIKE_FACTOR)

        if not is_volume_spike:
            return None, {}

        # 2. 分析K线形态
        body_size = abs(candle['close'] - candle['open'])
        upper_shadow = candle['high'] - max(candle['open'], candle['close'])
        lower_shadow = min(candle['open'], candle['close']) - candle['low']
        candle_range = candle['high'] - candle['low']

        details = {
            'volume': candle['volume'],
            'avg_volume': avg_volume,
            'is_volume_spike': is_volume_spike,
            'trigger_candle_time': candle.name,
        }

        # 形态一: 射击之星 (长上影, 不关心颜色)
        # 条件: 上影线是实体的N倍, 且上影线也是下影线的N倍, 避免长腿十字
        if body_size > 1e-9 and \
                upper_shadow > body_size * params.TRIGGER_SHADOW_FACTOR and \
                upper_shadow > lower_shadow * params.TRIGGER_SHADOW_FACTOR:
            details.update({
                'pattern': 'Shooting Star',
                'upper_shadow': upper_shadow,
                'body_size': body_size,
                'lower_shadow': lower_shadow,
                'shadow_factor_used': params.TRIGGER_SHADOW_FACTOR,
            })
            return "Shooting Star Pattern", details

        # 形态二: 量价背离 (放量收小阳线实体)
        # 条件: 实体很小(相对于总振幅), 且是阳线(代表努力)
        if candle_range > 1e-9 and \
                (body_size / candle_range) < params.TRIGGER_SMALL_BODY_THRESHOLD_PCT and \
                candle['close'] > candle['open']:
            details.update({
                'pattern': 'Bearish Divergence',
                'body_size': body_size,
                'candle_range': candle_range,
                'body_to_range_ratio': body_size / candle_range,
                'threshold_pct_used': params.TRIGGER_SMALL_BODY_THRESHOLD_PCT,
            })
            return "Bearish Volume-Price Divergence", details

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
