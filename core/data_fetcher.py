"""
数据获取模块
使用币安API异步获取多时间框架的K线数据
"""
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceOrderException
from loguru import logger

from config.config import config, system_params


class DataFetcher:
    """币安数据获取器 - 异步版本"""
    
    def __init__(self):
        """初始化数据获取器"""
        self.client: Optional[AsyncClient] = None
        self.is_connected: bool = False
        self.klines_limit = config.KLINES_LIMIT
        self.timeframes = config.TIMEFRAMES  # 从配置中获取所有时间框架
        
    async def initialize(self) -> bool:
        """初始化连接"""
        try:
            api_key, api_secret = config.get_api_credentials()
            
            if not api_key or not api_secret:
                logger.error("API凭证未配置！请检查.env文件")
                return False
                
            # 创建异步客户端
            if config.USE_TESTNET:
                self.client = AsyncClient(api_key, api_secret, tld='com', testnet=True)
                logger.info("已连接到币安测试网")
            else:
                self.client = AsyncClient(api_key, api_secret, tld='com')
                logger.info("已连接到币安主网")
            
            # 测试连接，如果失败则直接返回False
            if not await self.test_connection():
                logger.error("API连接测试失败，无法继续初始化。请检查您的网络、API密钥或系统时间。")
                return False

            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"初始化币安客户端失败: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """测试API连接"""
        try:
            server_time = await self.client.get_server_time()
            logger.info(f"币安服务器时间: {datetime.fromtimestamp(server_time['serverTime']/1000)}")
            
            # 测试账户信息访问
            account_info = await self.client.get_account()
            logger.info("API连接测试成功")
            
            return True
            
        except Exception as e:
            logger.error(f"API连接测试失败: {e}")
            return False
    
    async def get_klines_data(
        self, 
        symbol: str, 
        interval: str, 
        limit: int = None
    ) -> pd.DataFrame:
        """
        获取单个交易对的K线数据
        
        Args:
            symbol: 交易对符号 (如 'ETHUSDT')
            interval: 时间间隔 (如 '5m', '2h')
            limit: 获取数量限制
        
        Returns:
            包含OHLCV数据的DataFrame
        """
        if not self.is_connected:
            raise RuntimeError("数据获取器未初始化，请先调用initialize()")
        
        try:
            limit = limit or self.klines_limit
            
            # 获取K线数据
            klines = await self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            # 转换为DataFrame
            df = self._klines_to_dataframe(klines)
            
            logger.debug(f"成功获取 {symbol} {interval} K线数据: {len(df)} 条")
            return df
            
        except BinanceAPIException as e:
            logger.error(f"获取K线数据API错误 {symbol}-{interval}: {e}")
            raise
        except Exception as e:
            logger.error(f"获取 {symbol} 在 {interval} 的K线数据失败: {e}")
            return None
    
    async def get_multi_timeframe_data(
        self,
        symbol: str,
        major_timeframe: str = None,
        minor_timeframe: str = None,
        limit: int = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        获取多时间框架数据 (大周期和小周期)
        
        Args:
            symbol: 交易对符号
            major_timeframe: 大周期时间框架
            minor_timeframe: 小周期时间框架
            limit: 数据获取限制
        
        Returns:
            (大周期数据, 小周期数据) 元组
        """
        major_tf = major_timeframe or config.MAJOR_TIMEFRAME
        minor_tf = minor_timeframe or config.MINOR_TIMEFRAME
        limit = limit or config.KLINES_LIMIT
        
        try:
            # 并发获取两个时间框架的数据
            major_task = self.get_klines_data(symbol, major_tf, limit)
            minor_task = self.get_klines_data(symbol, minor_tf, limit)
            
            major_data, minor_data = await asyncio.gather(
                major_task, 
                minor_task,
                return_exceptions=True
            )
            
            # 检查是否有异常
            if isinstance(major_data, Exception):
                raise major_data
            if isinstance(minor_data, Exception):
                raise minor_data
            
            logger.info(f"成功获取 {symbol} 多时间框架数据: {major_tf}({len(major_data)}条), {minor_tf}({len(minor_data)}条)")
            
            return major_data, minor_data
            
        except Exception as e:
            logger.error(f"获取多时间框架数据失败 {symbol}: {e}")
            raise
    
    async def get_all_timeframes_data(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """
        一次性异步获取单个交易对的所有预设时间框架的K线数据。
        这是策略V2.1需要的主要数据获取函数。
        """
        tasks = [self.get_klines_data(symbol, tf) for tf in self.timeframes]
        results = await asyncio.gather(*tasks)
        
        data_dict = {}
        for tf, df in zip(self.timeframes, results):
            if df is not None and not df.empty:
                data_dict[tf] = df
            else:
                logger.warning(f"无法获取 {symbol} 在 {tf} 的数据，将跳过此时间框架。")
                # 返回一个空字典，让上层知道数据不完整
                return {}
        
        return data_dict
    
    async def get_all_pairs_data(
        self,
        pairs: List[str] = None,
        major_timeframe: str = None,
        minor_timeframe: str = None
    ) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        获取所有交易对的多时间框架数据
        
        Args:
            pairs: 交易对列表
            major_timeframe: 大周期时间框架
            minor_timeframe: 小周期时间框架
        
        Returns:
            {交易对: (大周期数据, 小周期数据)} 字典
        """
        pairs = pairs or config.TRADING_PAIRS
        
        try:
            # 为每个交易对创建获取任务
            tasks = []
            for pair in pairs:
                task = self.get_multi_timeframe_data(
                    pair, major_timeframe, minor_timeframe
                )
                tasks.append((pair, task))
            
            # 并发执行所有任务
            results = {}
            for pair, task in tasks:
                try:
                    major_data, minor_data = await task
                    results[pair] = (major_data, minor_data)
                except Exception as e:
                    logger.error(f"获取 {pair} 数据失败: {e}")
                    # 继续处理其他交易对，不中断整个流程
                    continue
            
            logger.info(f"成功获取 {len(results)}/{len(pairs)} 个交易对的数据")
            return results
            
        except Exception as e:
            logger.error(f"获取所有交易对数据失败: {e}")
            raise
    
    def _klines_to_dataframe(self, klines: List[List]) -> pd.DataFrame:
        """
        将K线数据转换为DataFrame
        
        Args:
            klines: 币安API返回的K线数据
        
        Returns:
            格式化的DataFrame
        """
        columns = [
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]
        
        df = pd.DataFrame(klines, columns=columns)
        
        # 数据类型转换
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 
                          'quote_asset_volume', 'taker_buy_base_asset_volume', 
                          'taker_buy_quote_asset_volume']
        
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 时间戳转换
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        
        # 设置时间戳为索引
        df.set_index('timestamp', inplace=True)
        
        # 删除不需要的列
        df.drop(['ignore'], axis=1, inplace=True)
        
        # 确保数据按时间排序
        df.sort_index(inplace=True)
        
        return df
    
    async def get_current_price(self, symbol: str) -> float:
        """
        获取当前价格
        
        Args:
            symbol: 交易对符号
        
        Returns:
            当前价格
        """
        try:
            ticker = await self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"获取 {symbol} 当前价格失败: {e}")
            raise
    
    async def get_market_data_summary(self, symbol: str) -> Dict[str, Any]:
        """
        获取市场数据摘要
        
        Args:
            symbol: 交易对符号
        
Returns:
            市场数据摘要
        """
        try:
            ticker_24hr = await self.client.get_ticker(symbol=symbol)
            
            summary = {
                'symbol': symbol,
                'current_price': float(ticker_24hr['lastPrice']),
                'price_change_24h': float(ticker_24hr['priceChange']),
                'price_change_percent_24h': float(ticker_24hr['priceChangePercent']),
                'high_24h': float(ticker_24hr['highPrice']),
                'low_24h': float(ticker_24hr['lowPrice']),
                'volume_24h': float(ticker_24hr['volume']),
                'quote_volume_24h': float(ticker_24hr['quoteVolume']),
                'timestamp': datetime.now()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取 {symbol} 市场数据摘要失败: {e}")
            raise
    
    async def close(self) -> None:
        """关闭连接"""
        if self.client:
            await self.client.close_connection()
            self.is_connected = False
            logger.info("币安客户端连接已关闭")

    async def fetch_historical_klines(self, symbol: str, interval: str, end_dt: datetime) -> Optional[pd.DataFrame]:
        """
        [新增] 获取指定结束时间点的历史K线数据。
        这是策略复盘功能的核心。
        """
        try:
            # python-binance 使用毫秒级时间戳字符串
            end_str = str(int(end_dt.timestamp() * 1000))
            
            # 调用API获取历史数据
            klines = await self.client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                end_str=end_str,
                limit=self.klines_limit
            )

            if not klines:
                logger.warning(f"在 {end_dt} 未找到 {symbol}-{interval} 的历史数据。")
                return None

            # 将原始数据转换为pandas DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades', 
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # 数据类型转换
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
            
            # 将时间戳设置为索引
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
        except Exception as e:
            logger.error(f"获取 {symbol} 在 {interval} 的历史K线数据时失败 (截至 {end_dt}): {e}", exc_info=True)
            return None


# 创建全局数据获取器实例
data_fetcher = DataFetcher()

# 便捷函数
async def get_market_data(symbol: str = None) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
    """便捷函数：获取市场数据"""
    if not data_fetcher.is_connected:
        await data_fetcher.initialize()
    
    if symbol:
        major_data, minor_data = await data_fetcher.get_multi_timeframe_data(symbol)
        return {symbol: (major_data, minor_data)}
    else:
        return await data_fetcher.get_all_pairs_data()


# 导出
__all__ = ['DataFetcher', 'data_fetcher', 'get_market_data'] 