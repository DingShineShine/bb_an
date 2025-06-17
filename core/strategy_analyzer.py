"""
策略分析模块 - 项目的"大脑"
实现"顺大势，逆小势"的多时间框架交易策略
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from loguru import logger

from config.config import strategy_params, indicator_params
from core.indicator_calculator import indicator_calculator


class StrategyAnalyzer:
    """
    核心策略分析器
    实现多时间框架交易策略：
    - 2H图判断大趋势
    - 5M图寻找入场点
    - RSI背离作为核心信号
    """
    
    def __init__(self):
        """初始化策略分析器"""
        self.strategy_params = strategy_params
        self.indicator_params = indicator_params
    
    def analyze(
        self, 
        symbol: str,
        data_2h: pd.DataFrame, 
        data_5m: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        核心分析函数 - 策略的主入口
        
        Args:
            symbol: 交易对符号
            data_2h: 2小时图数据 (大周期)
            data_5m: 5分钟图数据 (小周期)
        
        Returns:
            交易决策字典
        """
        try:
            logger.info(f"开始分析 {symbol} 的交易机会...")
            
            # 1. 计算所有技术指标
            data_2h_with_indicators = indicator_calculator.calculate_all_indicators(data_2h)
            data_5m_with_indicators = indicator_calculator.calculate_all_indicators(data_5m)
            
            # 2. 大周期趋势分析 (2H)
            major_trend = self._analyze_major_trend(data_2h_with_indicators)
            logger.info(f"{symbol} 大周期趋势: {major_trend['direction']} (强度: {major_trend['strength']:.2f})")
            
            # 3. 检查是否为震荡市 - 震荡市不交易！
            if major_trend['direction'] == 'SIDEWAYS':
                return {
                    'symbol': symbol,
                    'decision': 'WAIT',
                    'reason': '大周期处于震荡市，暂时观望',
                    'confidence': 0.0,
                    'major_trend': major_trend,
                    'minor_signals': {},
                    'timestamp': datetime.now()
                }
            
            # 4. 小周期信号分析 (5M)
            minor_signals = self._analyze_minor_signals(
                data_5m_with_indicators, 
                major_trend['direction']
            )
            
            # 5. 生成交易决策
            decision = self._generate_trading_decision(
                symbol, major_trend, minor_signals
            )
            
            logger.info(f"{symbol} 分析完成: {decision['decision']} (置信度: {decision['confidence']:.2f})")
            
            return decision
            
        except Exception as e:
            logger.error(f"分析 {symbol} 时发生错误: {e}")
            return {
                'symbol': symbol,
                'decision': 'ERROR',
                'reason': f'分析过程中发生错误: {str(e)}',
                'confidence': 0.0,
                'timestamp': datetime.now()
            }
    
    def _analyze_major_trend(self, data_2h: pd.DataFrame) -> Dict[str, Any]:
        """
        分析大周期趋势 (2H图)
        判断当前是上涨、下跌还是震荡趋势
        
        核心逻辑：
        - 上涨趋势: 价格 > EMA(10) > EMA(20) 且均线向上
        - 下跌趋势: 价格 < EMA(10) < EMA(20) 且均线向下  
        - 震荡市: 均线走平、反复缠绕
        """
        try:
            if len(data_2h) < 20:
                return {'direction': 'UNKNOWN', 'strength': 0.0, 'details': {}}
            
            # 获取最近几根K线进行分析
            recent_periods = self.strategy_params.TREND_CONFIRMATION_PERIODS
            recent_data = data_2h.tail(recent_periods)
            latest = data_2h.iloc[-1]
            
            # 基础趋势条件检查
            trend_analysis = {
                'direction': 'SIDEWAYS',
                'strength': 0.0,
                'details': {
                    'current_price': latest['close'],
                    'ema_10': latest['ema_10'],
                    'ema_20': latest['ema_20'],
                    'ema_fast_slope': latest['ema_fast_slope'],
                    'ema_slow_slope': latest['ema_slow_slope'],
                    'trend_bullish_count': recent_data['trend_bullish'].sum(),
                    'trend_bearish_count': recent_data['trend_bearish'].sum(),
                    'trend_sideways_count': recent_data['trend_sideways'].sum()
                }
            }
            
            # 判断趋势方向
            bullish_signals = 0
            bearish_signals = 0
            
            # 1. EMA排列检查
            if latest['close'] > latest['ema_10'] > latest['ema_20']:
                bullish_signals += 2
            elif latest['close'] < latest['ema_10'] < latest['ema_20']:
                bearish_signals += 2
            
            # 2. EMA斜率检查 (均线方向)
            if latest['ema_fast_slope'] > 0 and latest['ema_slow_slope'] > 0:
                bullish_signals += 1
            elif latest['ema_fast_slope'] < 0 and latest['ema_slow_slope'] < 0:
                bearish_signals += 1
            
            # 3. 趋势持续性检查
            if recent_data['trend_bullish'].sum() >= recent_periods - 1:
                bullish_signals += 1
            elif recent_data['trend_bearish'].sum() >= recent_periods - 1:
                bearish_signals += 1
            
            # 4. 市场结构检查 (Higher Lows / Lower Highs)
            market_structure = self._analyze_market_structure(data_2h.tail(10))
            if market_structure['higher_lows']:
                bullish_signals += 1
            elif market_structure['lower_highs']:
                bearish_signals += 1
            
            # 确定趋势方向和强度
            total_signals = bullish_signals + bearish_signals
            
            if bullish_signals >= 3:
                trend_analysis['direction'] = 'BULLISH'
                trend_analysis['strength'] = min(bullish_signals / 5.0, 1.0)
            elif bearish_signals >= 3:
                trend_analysis['direction'] = 'BEARISH'
                trend_analysis['strength'] = min(bearish_signals / 5.0, 1.0)
            else:
                # 震荡市判断
                trend_analysis['direction'] = 'SIDEWAYS'
                trend_analysis['strength'] = 0.0
            
            trend_analysis['details']['bullish_signals'] = bullish_signals
            trend_analysis['details']['bearish_signals'] = bearish_signals
            trend_analysis['details']['market_structure'] = market_structure
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"分析大周期趋势失败: {e}")
            return {'direction': 'UNKNOWN', 'strength': 0.0, 'details': {}}
    
    def _analyze_minor_signals(
        self, 
        data_5m: pd.DataFrame, 
        major_trend_direction: str
    ) -> Dict[str, Any]:
        """
        分析小周期信号 (5M图)
        根据大周期趋势寻找入场点
        
        核心逻辑：
        - 大周期上涨：在5M回调低点寻找做多机会
        - 大周期下跌：在5M反弹高点寻找做空机会
        - 主要信号：RSI背离
        - 辅助信号：价格行为、支撑阻力位
        """
        try:
            signals = {
                'rsi_divergence': {},
                'price_action': {},
                'support_resistance': {},
                'entry_conditions': {},
                'signal_strength': 0.0
            }
            
            if len(data_5m) < 50:
                return signals
            
            # 1. RSI背离检测 - 核心信号！
            divergence = indicator_calculator.detect_rsi_divergence(data_5m)
            signals['rsi_divergence'] = divergence
            
            # 2. 当前市场状态
            current_state = indicator_calculator.get_current_market_state(data_5m)
            signals['current_state'] = current_state
            
            # 3. 根据大周期趋势寻找相应的入场信号
            if major_trend_direction == 'BULLISH':
                # 大周期上涨 - 寻找5M回调底部做多
                entry_signals = self._find_bullish_entry_signals(data_5m, divergence, current_state)
            elif major_trend_direction == 'BEARISH':
                # 大周期下跌 - 寻找5M反弹顶部做空
                entry_signals = self._find_bearish_entry_signals(data_5m, divergence, current_state)
            else:
                entry_signals = {'valid': False, 'reasons': ['大周期趋势不明确']}
            
            signals['entry_conditions'] = entry_signals
            
            # 4. 计算综合信号强度
            signals['signal_strength'] = self._calculate_signal_strength(
                divergence, entry_signals, current_state
            )
            
            return signals
            
        except Exception as e:
            logger.error(f"分析小周期信号失败: {e}")
            return {'signal_strength': 0.0}
    
    def _find_bullish_entry_signals(
        self, 
        data_5m: pd.DataFrame, 
        divergence: Dict, 
        current_state: Dict
    ) -> Dict[str, Any]:
        """
        寻找做多入场信号
        大周期上涨趋势中，在5M回调底部寻找做多机会
        """
        entry_signals = {
            'valid': False,
            'reasons': [],
            'strength': 0.0,
            'conditions_met': []
        }
        
        signal_count = 0
        max_signals = 5
        
        # 1. 核心条件：看涨RSI背离
        if divergence.get('bullish_divergence', False):
            signal_count += 2  # RSI背离是最重要的信号
            entry_signals['conditions_met'].append('看涨RSI背离')
        
        # 2. 位置条件：接近支撑位
        if current_state.get('near_support', False):
            signal_count += 1
            entry_signals['conditions_met'].append('接近支撑位')
        
        # 3. RSI超卖
        if current_state.get('rsi', 50) < self.indicator_params.RSI_OVERSOLD:
            signal_count += 1
            entry_signals['conditions_met'].append('RSI超卖')
        
        # 4. 价格行为确认
        if current_state.get('bullish_engulfing', False):
            signal_count += 1
            entry_signals['conditions_met'].append('看涨吞没形态')
        
        # 5. 价格位于EMA之下（回调确认）
        if current_state.get('price', 0) < current_state.get('ema_fast', 0):
            signal_count += 1
            entry_signals['conditions_met'].append('价格回调至EMA下方')
        
        # 评估信号有效性
        entry_signals['strength'] = signal_count / max_signals
        
        if signal_count >= 2 and divergence.get('bullish_divergence', False):
            entry_signals['valid'] = True
            entry_signals['reasons'].append(f'满足{signal_count}个做多条件，包含关键的RSI看涨背离')
        else:
            entry_signals['reasons'].append(f'仅满足{signal_count}个条件，缺少关键信号')
        
        return entry_signals
    
    def _find_bearish_entry_signals(
        self, 
        data_5m: pd.DataFrame, 
        divergence: Dict, 
        current_state: Dict
    ) -> Dict[str, Any]:
        """
        寻找做空入场信号
        大周期下跌趋势中，在5M反弹顶部寻找做空机会
        """
        entry_signals = {
            'valid': False,
            'reasons': [],
            'strength': 0.0,
            'conditions_met': []
        }
        
        signal_count = 0
        max_signals = 5
        
        # 1. 核心条件：看跌RSI背离
        if divergence.get('bearish_divergence', False):
            signal_count += 2  # RSI背离是最重要的信号
            entry_signals['conditions_met'].append('看跌RSI背离')
        
        # 2. 位置条件：接近阻力位
        if current_state.get('near_resistance', False):
            signal_count += 1
            entry_signals['conditions_met'].append('接近阻力位')
        
        # 3. RSI超买
        if current_state.get('rsi', 50) > self.indicator_params.RSI_OVERBOUGHT:
            signal_count += 1
            entry_signals['conditions_met'].append('RSI超买')
        
        # 4. 价格行为确认
        if current_state.get('bearish_engulfing', False):
            signal_count += 1
            entry_signals['conditions_met'].append('看跌吞没形态')
        
        # 5. 价格位于EMA之上（反弹确认）
        if current_state.get('price', 0) > current_state.get('ema_fast', 0):
            signal_count += 1
            entry_signals['conditions_met'].append('价格反弹至EMA上方')
        
        # 评估信号有效性
        entry_signals['strength'] = signal_count / max_signals
        
        if signal_count >= 2 and divergence.get('bearish_divergence', False):
            entry_signals['valid'] = True
            entry_signals['reasons'].append(f'满足{signal_count}个做空条件，包含关键的RSI看跌背离')
        else:
            entry_signals['reasons'].append(f'仅满足{signal_count}个条件，缺少关键信号')
        
        return entry_signals
    
    def _analyze_market_structure(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析市场结构
        检测Higher Lows (上涨趋势) 和 Lower Highs (下跌趋势)
        """
        try:
            if len(data) < 6:
                return {'higher_lows': False, 'lower_highs': False}
            
            # 寻找局部高低点
            highs = data['high'].values
            lows = data['low'].values
            
            # 简化的市场结构分析
            recent_highs = []
            recent_lows = []
            
            # 寻找最近的高点和低点
            for i in range(2, len(data) - 2):
                if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                    highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                    recent_highs.append(highs[i])
                
                if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                    lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                    recent_lows.append(lows[i])
            
            # 分析趋势
            higher_lows = False
            lower_highs = False
            
            if len(recent_lows) >= 2:
                higher_lows = recent_lows[-1] > recent_lows[-2]
            
            if len(recent_highs) >= 2:
                lower_highs = recent_highs[-1] < recent_highs[-2]
            
            return {
                'higher_lows': higher_lows,
                'lower_highs': lower_highs,
                'recent_highs': recent_highs,
                'recent_lows': recent_lows
            }
            
        except Exception as e:
            logger.error(f"分析市场结构失败: {e}")
            return {'higher_lows': False, 'lower_highs': False}
    
    def _calculate_signal_strength(
        self, 
        divergence: Dict, 
        entry_signals: Dict, 
        current_state: Dict
    ) -> float:
        """计算综合信号强度"""
        try:
            strength = 0.0
            
            # RSI背离权重 (最重要)
            divergence_strength = divergence.get('divergence_strength', 0.0)
            strength += divergence_strength * 0.5
            
            # 入场条件权重
            entry_strength = entry_signals.get('strength', 0.0)
            strength += entry_strength * 0.3
            
            # 位置权重 (支撑阻力位)
            if current_state.get('near_support') or current_state.get('near_resistance'):
                strength += 0.2
            
            return min(strength, 1.0)
            
        except Exception as e:
            logger.error(f"计算信号强度失败: {e}")
            return 0.0
    
    def _generate_trading_decision(
        self, 
        symbol: str,
        major_trend: Dict, 
        minor_signals: Dict
    ) -> Dict[str, Any]:
        """
        生成最终交易决策
        综合大小周期分析结果，给出明确的交易建议
        """
        try:
            decision = {
                'symbol': symbol,
                'decision': 'WAIT',
                'reason': '',
                'confidence': 0.0,
                'major_trend': major_trend,
                'minor_signals': minor_signals,
                'recommended_action': {},
                'timestamp': datetime.now()
            }
            
            # 获取关键信息
            major_direction = major_trend.get('direction', 'UNKNOWN')
            major_strength = major_trend.get('strength', 0.0)
            signal_strength = minor_signals.get('signal_strength', 0.0)
            entry_conditions = minor_signals.get('entry_conditions', {})
            
            # 决策逻辑
            if major_direction == 'SIDEWAYS':
                decision.update({
                    'decision': 'WAIT',
                    'reason': '大周期处于震荡市，不符合交易条件',
                    'confidence': 0.0
                })
            
            elif major_direction == 'BULLISH' and entry_conditions.get('valid', False):
                # 大周期上涨 + 小周期做多信号
                confidence = min((major_strength + signal_strength) / 2, 1.0)
                
                if confidence >= self.strategy_params.HIGH_CONFIDENCE_THRESHOLD:
                    decision.update({
                        'decision': 'LONG',
                        'reason': f'大周期上涨趋势 + 5M回调做多信号 (RSI背离)',
                        'confidence': confidence,
                        'recommended_action': {
                            'direction': 'LONG',
                            'entry_reason': '看涨RSI背离 + 回调至支撑位',
                            'conditions_met': entry_conditions.get('conditions_met', [])
                        }
                    })
                elif confidence >= self.strategy_params.MEDIUM_CONFIDENCE_THRESHOLD:
                    decision.update({
                        'decision': 'LONG_WEAK',
                        'reason': f'中等强度做多信号，建议谨慎操作',
                        'confidence': confidence
                    })
                else:
                    decision.update({
                        'decision': 'WAIT',
                        'reason': f'做多信号较弱，继续观望',
                        'confidence': confidence
                    })
            
            elif major_direction == 'BEARISH' and entry_conditions.get('valid', False):
                # 大周期下跌 + 小周期做空信号
                confidence = min((major_strength + signal_strength) / 2, 1.0)
                
                if confidence >= self.strategy_params.HIGH_CONFIDENCE_THRESHOLD:
                    decision.update({
                        'decision': 'SHORT',
                        'reason': f'大周期下跌趋势 + 5M反弹做空信号 (RSI背离)',
                        'confidence': confidence,
                        'recommended_action': {
                            'direction': 'SHORT',
                            'entry_reason': '看跌RSI背离 + 反弹至阻力位',
                            'conditions_met': entry_conditions.get('conditions_met', [])
                        }
                    })
                elif confidence >= self.strategy_params.MEDIUM_CONFIDENCE_THRESHOLD:
                    decision.update({
                        'decision': 'SHORT_WEAK',
                        'reason': f'中等强度做空信号，建议谨慎操作',
                        'confidence': confidence
                    })
                else:
                    decision.update({
                        'decision': 'WAIT',
                        'reason': f'做空信号较弱，继续观望',
                        'confidence': confidence
                    })
            
            else:
                decision.update({
                    'decision': 'WAIT',
                    'reason': '未满足入场条件，继续等待机会',
                    'confidence': 0.0
                })
            
            return decision
            
        except Exception as e:
            logger.error(f"生成交易决策失败: {e}")
            return {
                'symbol': symbol,
                'decision': 'ERROR',
                'reason': f'决策生成错误: {str(e)}',
                'confidence': 0.0,
                'timestamp': datetime.now()
            }


# 创建全局策略分析器实例
strategy_analyzer = StrategyAnalyzer()

# 便捷函数
def analyze_trading_opportunity(
    symbol: str,
    data_2h: pd.DataFrame, 
    data_5m: pd.DataFrame
) -> Dict[str, Any]:
    """便捷函数：分析交易机会"""
    return strategy_analyzer.analyze(symbol, data_2h, data_5m)

# 导出
__all__ = ['StrategyAnalyzer', 'strategy_analyzer', 'analyze_trading_opportunity'] 