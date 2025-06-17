"""
BinanceEventTrader 配置文件
包含API配置、交易对和策略参数等核心配置
"""
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """主配置类"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # =============================================================================
    # API配置
    # =============================================================================
    BINANCE_API_KEY: str = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET: str = os.getenv('BINANCE_API_SECRET', '')
    
    # 测试网配置 (用于开发测试)
    USE_TESTNET: bool = os.getenv('USE_TESTNET', 'True').lower() == 'true'
    TESTNET_API_KEY: str = os.getenv('BINANCE_TESTNET_API_KEY', '')
    TESTNET_API_SECRET: str = os.getenv('BINANCE_TESTNET_SECRET_KEY', '')
    
    # =============================================================================
    # 交易对配置
    # =============================================================================
    TRADING_PAIRS: List[str] = ['ETHUSDT', 'BTCUSDT']
    
    # =============================================================================
    # 时间框架配置
    # =============================================================================
    # 大周期：用于趋势判断
    MAJOR_TIMEFRAME: str = '2h'
    # 小周期：用于入场点寻找
    MINOR_TIMEFRAME: str = '5m'
    
    # K线数据获取数量
    KLINES_LIMIT: int = 200
    
    # =============================================================================
    # 技术指标参数
    # =============================================================================
    class IndicatorParams:
        """技术指标参数配置"""
        
        # EMA参数
        EMA_FAST: int = 10      # 快速EMA周期
        EMA_SLOW: int = 20      # 慢速EMA周期
        
        # RSI参数
        RSI_PERIOD: int = 14    # RSI计算周期
        RSI_OVERBOUGHT: float = 70.0    # RSI超买阈值
        RSI_OVERSOLD: float = 30.0      # RSI超卖阈值
        
        # 背离检测参数
        DIVERGENCE_LOOKBACK: int = 20   # 背离检测回看周期
        MIN_DIVERGENCE_BARS: int = 5    # 最小背离K线数量
    
    # =============================================================================
    # 策略配置
    # =============================================================================
    class StrategyParams:
        """策略参数配置"""
        
        # 趋势判断参数
        TREND_CONFIRMATION_PERIODS: int = 3  # 趋势确认需要的周期数
        SIDEWAYS_THRESHOLD: float = 0.5      # 震荡市判断阈值(%)
        
        # 信号强度阈值
        HIGH_CONFIDENCE_THRESHOLD: float = 0.8
        MEDIUM_CONFIDENCE_THRESHOLD: float = 0.6
        
        # 风险管理参数
        MAX_RISK_PER_TRADE: float = 0.02    # 单笔交易最大风险(2%)
        STOP_LOSS_RATIO: float = 0.015      # 止损比例(1.5%)
        TAKE_PROFIT_RATIO: float = 0.03     # 止盈比例(3%)
    
    # =============================================================================
    # 系统配置
    # =============================================================================
    class SystemParams:
        """系统运行参数"""
        
        # 数据更新频率(秒)
        DATA_UPDATE_INTERVAL: int = 60
        
        # 日志配置
        LOG_LEVEL: str = 'INFO'
        LOG_FORMAT: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        
        # 请求限制
        MAX_REQUESTS_PER_MINUTE: int = 1200
        REQUEST_TIMEOUT: int = 30
    
    # =============================================================================
    # 事件合约配置
    # =============================================================================
    class EventContractParams:
        """币安事件合约参数"""
        
        # 合约持续时间(分钟)
        CONTRACT_DURATION: int = 10
        
        # 最小下单金额(USDT)
        MIN_ORDER_SIZE: float = 1.0
        
        # 最大下单金额(USDT)
        MAX_ORDER_SIZE: float = 100.0
        
        # 默认下单金额(USDT)
        DEFAULT_ORDER_SIZE: float = 10.0

    @classmethod
    def validate_config(cls) -> bool:
        from dotenv import load_dotenv
        load_dotenv()
        """验证配置的有效性"""
        if cls.USE_TESTNET:
            return bool(cls.TESTNET_API_KEY and cls.TESTNET_API_SECRET)
        else:
            return bool(cls.BINANCE_API_KEY and cls.BINANCE_API_SECRET)
    
    @classmethod
    def get_api_credentials(cls) -> tuple[str, str]:
        """获取API凭证"""
        if cls.USE_TESTNET:
            return cls.TESTNET_API_KEY, cls.TESTNET_API_SECRET
        else:
            return cls.BINANCE_API_KEY, cls.BINANCE_API_SECRET

# 创建全局配置实例
config = Config()
indicator_params = Config.IndicatorParams()
strategy_params = Config.StrategyParams()
system_params = Config.SystemParams()
event_contract_params = Config.EventContractParams()

# 导出常用配置
__all__ = [
    'config',
    'indicator_params', 
    'strategy_params',
    'system_params',
    'event_contract_params'
] 