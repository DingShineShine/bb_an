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
    # 策略V2.1所需的所有时间框架
    TIMEFRAMES: List[str] = ['1m', '5m', '15m', '30m', '2h']
    
    # 关键时间框架定义 (方便访问)
    TREND_TIMEFRAME: str = '2h'    # 大周期：用于趋势判断
    SIGNAL_TIMEFRAME: str = '1m'   # 小周期：用于寻找入场信号
    
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
        
        # V2.1 信号触发参数 (集中管理)
        PROXIMITY_THRESHOLD: float = 0.005   # 价格距离支撑/阻力位的接近阈值 (0.5%)
        VOLUME_SPIKE_FACTOR: float = 2.0     # 成交量放大因子 (正常均值的2倍)
        VOLUME_SHRINK_FACTOR: float = 0.5    # 成交量萎缩因子 (正常均值的0.5倍)
        UPPER_SHADOW_FACTOR: float = 2.0     # 上影线与实体比例因子 (上影线是实体的2倍)
        
        # V2.2 新增：聚集区判断阈值
        CLUSTER_THRESHOLD: float = 0.002     # 支撑/阻力聚集区判断阈值 (0.2%)
    
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

# --- 新增: 数据库配置 ---
# 定义数据持久化的根目录
# 在Docker容器内部，我们将其映射到 /app/data
# 在本地直接运行时，它就是项目根目录下的 'data' 文件夹
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 定义SQLite数据库文件的完整路径
# 我们的程序将在这个路径下创建并读写 trading_data.db 文件
DATABASE_FILE = os.path.join(DATA_DIR, 'trading_data.db')

# --- 新增: 日志配置 ---
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'trader.log')

# 确保数据和日志目录在程序启动时存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True) 