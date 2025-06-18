"""
技术指标计算模块
包含EMA、RSI、背离检测等核心技术指标的计算
"""
import pandas as pd
import numpy as np
# 兼容性处理
try:
    import pandas_ta as ta
except ImportError as e:
    print(f"pandas_ta导入警告: {e}")
    ta = None

from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

from config.config import indicator_params


class IndicatorCalculator:
    """技术指标计算器"""
    
    def __init__(self):
        """初始化指标计算器"""
        self.ema_fast_period = indicator_params.EMA_FAST
        self.ema_slow_period = indicator_params.EMA_SLOW
        self.rsi_period = indicator_params.RSI_PERIOD
        self.divergence_lookback = indicator_params.DIVERGENCE_LOOKBACK
        self.min_divergence_bars = indicator_params.MIN_DIVERGENCE_BARS
    
    def calculate_indicators_for_all_timeframes(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        为所有时间框架的数据计算所需的技术指标。
        这是策略V2.1的核心指标计算函数。
        """
        processed_data = {}
        for timeframe, df in data_dict.items():
            if df is not None and not df.empty:
                try:
                    # 为每个时间框架的df计算指标
                    df_with_indicators = self.calculate_all_indicators(df)
                    processed_data[timeframe] = df_with_indicators
                except Exception as e:
                    logger.error(f"在 {timeframe} 上计算指标失败: {e}")
                    # 如果一个时间框架失败，则整个数据无效
                    return {}
            else:
                logger.warning(f"跳过在 {timeframe} 上的指标计算，因为数据为空。")
                return {}
        
        return processed_data

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有需要的技术指标
        
        Args:
            df: 包含OHLCV数据的DataFrame
        
        Returns:
            添加了技术指标的DataFrame
        """
        try:
            df = df.copy()
            
            # 基础指标计算
            df = self._calculate_ema(df)
            df = self._calculate_rsi(df)

            # 为V2.1策略添加成交量均线
            df['volume_MA_20'] = df['volume'].rolling(window=5).mean()

            # 移除旧的、不再需要的复杂计算
            # df = self._calculate_price_action_signals(df)
            # df = self._analyze_trend(df)
            # df = self._calculate_support_resistance(df)
            
            logger.debug(f"成功为数据长度 {len(df)} 计算了基础指标 (EMA, RSI, Volume MA)")
            return df
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            raise
    
    def _calculate_ema_manual(self, data: pd.Series, period: int) -> pd.Series:
        """手动计算EMA，避免pandas_ta兼容性问题"""
        alpha = 2 / (period + 1)
        ema = data.ewm(alpha=alpha, adjust=False).mean()
        return ema
    
    def _calculate_rsi_manual(self, data: pd.Series, period: int = 14) -> pd.Series:
        """手动计算RSI，避免pandas_ta兼容性问题"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_ema(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算EMA指标"""
        try:
            # 优先使用pandas_ta，如果不可用则使用手动计算
            if ta is not None:
                try:
                    df[f'ema_{self.ema_fast_period}'] = ta.ema(df['close'], length=self.ema_fast_period)
                    df[f'ema_{self.ema_slow_period}'] = ta.ema(df['close'], length=self.ema_slow_period)
                except Exception:
                    # 如果pandas_ta出错，使用手动计算
                    df[f'ema_{self.ema_fast_period}'] = self._calculate_ema_manual(df['close'], self.ema_fast_period)
                    df[f'ema_{self.ema_slow_period}'] = self._calculate_ema_manual(df['close'], self.ema_slow_period)
            else:
                # 使用手动计算
                df[f'ema_{self.ema_fast_period}'] = self._calculate_ema_manual(df['close'], self.ema_fast_period)
                df[f'ema_{self.ema_slow_period}'] = self._calculate_ema_manual(df['close'], self.ema_slow_period)
            
            # EMA关系分析
            df['ema_bullish'] = (df[f'ema_{self.ema_fast_period}'] > df[f'ema_{self.ema_slow_period}'])
            df['ema_bearish'] = (df[f'ema_{self.ema_fast_period}'] < df[f'ema_{self.ema_slow_period}'])
            
            # EMA斜率 (用于判断均线走向)
            df['ema_fast_slope'] = df[f'ema_{self.ema_fast_period}'].diff(periods=3)
            df['ema_slow_slope'] = df[f'ema_{self.ema_slow_period}'].diff(periods=3)
            
            # 价格与EMA关系
            df['price_above_ema_fast'] = df['close'] > df[f'ema_{self.ema_fast_period}']
            df['price_above_ema_slow'] = df['close'] > df[f'ema_{self.ema_slow_period}']
            
            return df
            
        except Exception as e:
            logger.error(f"计算EMA指标失败: {e}")
            raise
    
    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算RSI指标"""
        try:
            # 优先使用pandas_ta，如果不可用则使用手动计算
            if ta is not None:
                try:
                    df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
                except Exception:
                    # 如果pandas_ta出错，使用手动计算
                    df['rsi'] = self._calculate_rsi_manual(df['close'], self.rsi_period)
            else:
                # 使用手动计算
                df['rsi'] = self._calculate_rsi_manual(df['close'], self.rsi_period)
            
            # RSI区间分析
            df['rsi_overbought'] = df['rsi'] > indicator_params.RSI_OVERBOUGHT
            df['rsi_oversold'] = df['rsi'] < indicator_params.RSI_OVERSOLD
            
            # RSI趋势
            df['rsi_rising'] = df['rsi'] > df['rsi'].shift(1)
            df['rsi_falling'] = df['rsi'] < df['rsi'].shift(1)
            
            return df
            
        except Exception as e:
            logger.error(f"计算RSI指标失败: {e}")
            raise
    
    def _calculate_price_action_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算价格行为信号"""
        try:
            # 计算K线实体和影线
            df['body_size'] = abs(df['close'] - df['open'])
            df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
            df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
            df['total_range'] = df['high'] - df['low']
            
            # 吞没形态检测
            df['bullish_engulfing'] = self._detect_bullish_engulfing(df)
            df['bearish_engulfing'] = self._detect_bearish_engulfing(df)
            
            # 锤子线和吊颈线
            df['hammer'] = self._detect_hammer(df)
            df['hanging_man'] = self._detect_hanging_man(df)
            
            # 十字星
            df['doji'] = self._detect_doji(df)
            
            return df
            
        except Exception as e:
            logger.error(f"计算价格行为信号失败: {e}")
            raise
    
    def _detect_bullish_engulfing(self, df: pd.DataFrame) -> pd.Series:
        """检测看涨吞没形态"""
        condition = (
            (df['close'].shift(1) < df['open'].shift(1)) &  # 前一根K线是阴线
            (df['close'] > df['open']) &  # 当前K线是阳线
            (df['open'] < df['close'].shift(1)) &  # 当前开盘低于前一根收盘
            (df['close'] > df['open'].shift(1)) &  # 当前收盘高于前一根开盘
            (df['body_size'] > df['body_size'].shift(1))  # 当前实体大于前一根实体
        )
        return condition
    
    def _detect_bearish_engulfing(self, df: pd.DataFrame) -> pd.Series:
        """检测看跌吞没形态"""
        condition = (
            (df['close'].shift(1) > df['open'].shift(1)) &  # 前一根K线是阳线
            (df['close'] < df['open']) &  # 当前K线是阴线
            (df['open'] > df['close'].shift(1)) &  # 当前开盘高于前一根收盘
            (df['close'] < df['open'].shift(1)) &  # 当前收盘低于前一根开盘
            (df['body_size'] > df['body_size'].shift(1))  # 当前实体大于前一根实体
        )
        return condition
    
    def _detect_hammer(self, df: pd.DataFrame) -> pd.Series:
        """检测锤子线"""
        condition = (
            (df['lower_shadow'] >= 2 * df['body_size']) &  # 下影线至少是实体的2倍
            (df['upper_shadow'] <= 0.1 * df['body_size']) &  # 上影线很小
            (df['body_size'] > 0)  # 有实体
        )
        return condition
    
    def _detect_hanging_man(self, df: pd.DataFrame) -> pd.Series:
        """检测吊颈线"""
        # 吊颈线的形态与锤子线相同，但出现在上涨趋势中
        hammer_pattern = self._detect_hammer(df)
        uptrend = df['close'] > df['close'].shift(5)  # 简单的上涨趋势判断
        return hammer_pattern & uptrend
    
    def _detect_doji(self, df: pd.DataFrame) -> pd.Series:
        """检测十字星"""
        avg_body = df['body_size'].rolling(window=20).mean()
        condition = df['body_size'] <= 0.1 * avg_body
        return condition
    
    def _analyze_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """分析趋势状态"""
        try:
            # 基于EMA的趋势判断
            df['trend_bullish'] = (
                (df['close'] > df[f'ema_{self.ema_fast_period}']) &
                (df[f'ema_{self.ema_fast_period}'] > df[f'ema_{self.ema_slow_period}']) &
                (df['ema_fast_slope'] > 0) &
                (df['ema_slow_slope'] > 0)
            )
            
            df['trend_bearish'] = (
                (df['close'] < df[f'ema_{self.ema_fast_period}']) &
                (df[f'ema_{self.ema_fast_period}'] < df[f'ema_{self.ema_slow_period}']) &
                (df['ema_fast_slope'] < 0) &
                (df['ema_slow_slope'] < 0)
            )
            
            # 震荡市判断
            ema_distance = abs(df[f'ema_{self.ema_fast_period}'] - df[f'ema_{self.ema_slow_period}'])
            price_volatility = df['close'].rolling(window=20).std()
            
            df['trend_sideways'] = (
                (ema_distance < 0.005 * df['close']) &  # EMA距离很小
                (abs(df['ema_fast_slope']) < 0.001 * df['close']) &  # EMA斜率很小
                (abs(df['ema_slow_slope']) < 0.001 * df['close'])
            )
            
            return df
            
        except Exception as e:
            logger.error(f"分析趋势状态失败: {e}")
            raise
    
    def _calculate_support_resistance(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """计算支撑阻力位"""
        try:
            # 使用局部高低点识别支撑阻力
            df['local_high'] = df['high'].rolling(window=window, center=True).max() == df['high']
            df['local_low'] = df['low'].rolling(window=window, center=True).min() == df['low']
            
            # 计算近期的支撑阻力位
            recent_highs = df[df['local_high']]['high'].tail(5)
            recent_lows = df[df['local_low']]['low'].tail(5)
            
            # 动态支撑阻力位
            if len(recent_highs) > 0:
                df['resistance_level'] = recent_highs.mean()
            else:
                df['resistance_level'] = df['high'].rolling(window=50).max()
                
            if len(recent_lows) > 0:
                df['support_level'] = recent_lows.mean()
            else:
                df['support_level'] = df['low'].rolling(window=50).min()
            
            # 价格距离支撑阻力位的距离
            df['distance_to_resistance'] = (df['resistance_level'] - df['close']) / df['close']
            df['distance_to_support'] = (df['close'] - df['support_level']) / df['close']
            
            # 是否接近关键位置
            df['near_resistance'] = abs(df['distance_to_resistance']) < 0.01  # 1%以内
            df['near_support'] = abs(df['distance_to_support']) < 0.01  # 1%以内
            
            return df
            
        except Exception as e:
            logger.error(f"计算支撑阻力位失败: {e}")
            raise
    
    def detect_rsi_divergence(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        检测RSI背离
        这是我们策略的核心信号！
        
        Args:
            df: 包含价格和RSI数据的DataFrame
        
        Returns:
            背离检测结果字典
        """
        try:
            result = {
                'bullish_divergence': False,
                'bearish_divergence': False,
                'divergence_strength': 0.0,
                'divergence_details': {}
            }
            
            if len(df) < self.divergence_lookback:
                return result
            
            # 获取最近的数据进行分析
            recent_data = df.tail(self.divergence_lookback).copy()
            
            # 寻找价格的局部高点和低点
            price_peaks = self._find_peaks(recent_data['high'].values)
            price_troughs = self._find_troughs(recent_data['low'].values)
            
            # 寻找RSI的局部高点和低点
            rsi_peaks = self._find_peaks(recent_data['rsi'].values)
            rsi_troughs = self._find_troughs(recent_data['rsi'].values)
            
            # 检测看跌背离 (价格创新高，RSI未创新高)
            bearish_div = self._check_bearish_divergence(
                recent_data, price_peaks, rsi_peaks
            )
            
            # 检测看涨背离 (价格创新低，RSI未创新低)
            bullish_div = self._check_bullish_divergence(
                recent_data, price_troughs, rsi_troughs
            )
            
            result.update({
                'bullish_divergence': bullish_div['detected'],
                'bearish_divergence': bearish_div['detected'],
                'divergence_strength': max(bullish_div['strength'], bearish_div['strength']),
                'divergence_details': {
                    'bullish': bullish_div,
                    'bearish': bearish_div
                }
            })
            
            if result['bullish_divergence'] or result['bearish_divergence']:
                div_type = "看涨" if result['bullish_divergence'] else "看跌"
                logger.info(f"检测到{div_type}背离，强度: {result['divergence_strength']:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"检测RSI背离失败: {e}")
            return {'bullish_divergence': False, 'bearish_divergence': False, 
                   'divergence_strength': 0.0, 'divergence_details': {}}
    
    def _find_peaks(self, data: np.ndarray, min_distance: int = 3) -> List[int]:
        """寻找峰值"""
        peaks = []
        for i in range(min_distance, len(data) - min_distance):
            if all(data[i] >= data[i-j] for j in range(1, min_distance+1)) and \
               all(data[i] >= data[i+j] for j in range(1, min_distance+1)):
                peaks.append(i)
        return peaks
    
    def _find_troughs(self, data: np.ndarray, min_distance: int = 3) -> List[int]:
        """寻找谷值"""
        troughs = []
        for i in range(min_distance, len(data) - min_distance):
            if all(data[i] <= data[i-j] for j in range(1, min_distance+1)) and \
               all(data[i] <= data[i+j] for j in range(1, min_distance+1)):
                troughs.append(i)
        return troughs
    
    def _check_bearish_divergence(
        self, 
        df: pd.DataFrame, 
        price_peaks: List[int], 
        rsi_peaks: List[int]
    ) -> Dict[str, Any]:
        """检查看跌背离"""
        result = {'detected': False, 'strength': 0.0, 'details': {}}
        
        if len(price_peaks) < 2 or len(rsi_peaks) < 2:
            return result
        
        # 获取最近的两个峰值
        recent_price_peaks = sorted(price_peaks)[-2:]
        recent_rsi_peaks = sorted(rsi_peaks)[-2:]
        
        # 价格峰值
        price1 = df.iloc[recent_price_peaks[0]]['high']
        price2 = df.iloc[recent_price_peaks[1]]['high']
        
        # RSI峰值
        rsi1 = df.iloc[recent_rsi_peaks[0]]['rsi']
        rsi2 = df.iloc[recent_rsi_peaks[1]]['rsi']
        
        # 检查背离条件：价格新高，RSI未新高
        if price2 > price1 and rsi2 < rsi1:
            # 计算背离强度
            price_change = (price2 - price1) / price1
            rsi_change = (rsi1 - rsi2) / rsi1
            
            strength = min(price_change + rsi_change, 1.0)
            
            result = {
                'detected': True,
                'strength': strength,
                'details': {
                    'price1': price1,
                    'price2': price2,
                    'rsi1': rsi1,
                    'rsi2': rsi2,
                    'price_change': price_change,
                    'rsi_change': rsi_change
                }
            }
        
        return result
    
    def _check_bullish_divergence(
        self, 
        df: pd.DataFrame, 
        price_troughs: List[int], 
        rsi_troughs: List[int]
    ) -> Dict[str, Any]:
        """检查看涨背离"""
        result = {'detected': False, 'strength': 0.0, 'details': {}}
        
        if len(price_troughs) < 2 or len(rsi_troughs) < 2:
            return result
        
        # 获取最近的两个谷值
        recent_price_troughs = sorted(price_troughs)[-2:]
        recent_rsi_troughs = sorted(rsi_troughs)[-2:]
        
        # 价格谷值
        price1 = df.iloc[recent_price_troughs[0]]['low']
        price2 = df.iloc[recent_price_troughs[1]]['low']
        
        # RSI谷值
        rsi1 = df.iloc[recent_rsi_troughs[0]]['rsi']
        rsi2 = df.iloc[recent_rsi_troughs[1]]['rsi']
        
        # 检查背离条件：价格新低，RSI未新低
        if price2 < price1 and rsi2 > rsi1:
            # 计算背离强度
            price_change = (price1 - price2) / price1
            rsi_change = (rsi2 - rsi1) / rsi1
            
            strength = min(price_change + rsi_change, 1.0)
            
            result = {
                'detected': True,
                'strength': strength,
                'details': {
                    'price1': price1,
                    'price2': price2,
                    'rsi1': rsi1,
                    'rsi2': rsi2,
                    'price_change': price_change,
                    'rsi_change': rsi_change
                }
            }
        
        return result
    
    def get_current_market_state(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        获取当前市场状态摘要
        
        Args:
            df: 包含所有指标的DataFrame
        
        Returns:
            市场状态摘要
        """
        if len(df) == 0:
            return {}
        
        latest = df.iloc[-1]
        
        return {
            'price': latest['close'],
            'ema_fast': latest[f'ema_{self.ema_fast_period}'],
            'ema_slow': latest[f'ema_{self.ema_slow_period}'],
            'rsi': latest['rsi'],
            'trend_bullish': latest['trend_bullish'],
            'trend_bearish': latest['trend_bearish'],
            'trend_sideways': latest['trend_sideways'],
            'near_support': latest['near_support'],
            'near_resistance': latest['near_resistance'],
            'support_level': latest['support_level'],
            'resistance_level': latest['resistance_level'],
            'bullish_engulfing': latest['bullish_engulfing'],
            'bearish_engulfing': latest['bearish_engulfing']
        }


# 创建全局指标计算器实例
indicator_calculator = IndicatorCalculator()

# 便捷函数
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """便捷函数：计算技术指标"""
    return indicator_calculator.calculate_all_indicators(df)

def detect_divergence(df: pd.DataFrame) -> Dict[str, Any]:
    """便捷函数：检测背离"""
    return indicator_calculator.detect_rsi_divergence(df)

# 导出
__all__ = ['IndicatorCalculator', 'indicator_calculator', 'calculate_indicators', 'detect_divergence'] 