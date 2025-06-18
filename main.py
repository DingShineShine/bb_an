"""
BinanceEventTrader 主程序
币安事件合约自动化交易机器人
实现"顺大势，逆小势"的多时间框架交易策略
"""
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any
from loguru import logger
from collections import defaultdict

# 导入项目模块
from config.config import config, system_params, strategy_params
from core.data_fetcher import DataFetcher
from core.indicator_calculator import IndicatorCalculator
# 导入新的V2.1策略分析器
from core.strategy_analyzer import analyze_trading_opportunity_v2, StrategyAnalyzerV2
import json
import requests


class BinanceEventTrader:
    """币安事件合约交易机器人 (V2.1)"""
    
    def __init__(self):
        """初始化交易机器人"""
        self.is_running = False
        self.trading_enabled = False  # 初期设为False，仅进行分析和日志记录
        self._setup_logging()
        
        self.data_fetcher = DataFetcher()
        # 兼容旧版指标计算器，但主要使用其新方法
        self.indicator_calculator = IndicatorCalculator() 
        # 初始化新的V2.1策略分析器
        self.strategy_analyzer = StrategyAnalyzerV2()
        
    def _setup_logging(self):
        """配置日志系统"""
        logger.remove()  # 移除默认处理器
        
        # 控制台日志
        logger.add(
            sys.stdout,
            format=system_params.LOG_FORMAT,
            level=system_params.LOG_LEVEL,
            colorize=True
        )
        
        # 文件日志
        logger.add(
            "logs/binance_event_trader_{time:YYYY-MM-DD}.log",
            format=system_params.LOG_FORMAT,
            level="DEBUG",
            rotation="1 day",
            retention="30 days",
            compression="zip"
        )
        
        logger.add("logs/error.log", level="ERROR", rotation="10 MB", retention="7 days")
        logger.info("日志系统设置完成")
    
    async def initialize(self) -> bool:
        """初始化交易机器人"""
        try:
            logger.info("=== BinanceEventTrader 初始化开始 ===")
            
            # 1. 验证配置
            if not config.validate_config():
                logger.error("配置验证失败！请检查API密钥配置")
                return False
            
            logger.info(f"配置验证通过 (测试模式: {config.USE_TESTNET})")
            
            # 2. 初始化数据获取器，并严格检查其返回状态
            if not await self.data_fetcher.initialize():
                logger.error("数据获取器初始化失败。请再次检查您的API密钥、网络连接或系统时间同步设置。")
                return False
            
            logger.info("数据获取器初始化成功")
            
            # 3. 显示交易对信息
            logger.info(f"监控交易对: {config.TRADING_PAIRS}")
            logger.info(f"时间框架: 趋势周期({config.TREND_TIMEFRAME}) | 信号周期({config.SIGNAL_TIMEFRAME})")
            
            # 4. 显示策略参数
            logger.info("=== 策略参数 ===")
            logger.info(f"EMA周期: 快线({config.IndicatorParams.EMA_FAST}) | 慢线({config.IndicatorParams.EMA_SLOW})")
            logger.info(f"RSI周期: {config.IndicatorParams.RSI_PERIOD}")
            logger.info(f"背离检测回看周期: {config.IndicatorParams.DIVERGENCE_LOOKBACK}")
            
            logger.info("=== 初始化完成 ===")
            return True
            
        except Exception as e:
            logger.error(f"初始化过程中发生严重错误: {e}", exc_info=True)
            return False
    
    async def run(self):
        """运行主循环，按计划执行市场分析"""
        logger.info("主循环已启动，等待第一个任务执行点...")
        while self.is_running:
            try:
                # 新的休眠逻辑：先计算等待时间，再执行
                now = datetime.now()
                target_second = 1 # 目标在每分钟的第01秒执行

                # 判断下一个运行时间点是在当前分钟还是下一分钟
                if now.second < target_second:
                    next_run_time = now.replace(second=target_second, microsecond=0)
                else:
                    next_run_time = (now + timedelta(minutes=1)).replace(second=target_second, microsecond=0)
                
                wait_duration = (next_run_time - now).total_seconds()
                
                logger.info(f"===== 任务规划完成，下一次分析将在 {next_run_time.strftime('%H:%M:%S')} (等待 {wait_duration:.2f} 秒) =====")
                await asyncio.sleep(wait_duration)

                logger.info("===== 开始新一轮市场分析 =====")
                await self._analyze_markets()
                
            except asyncio.CancelledError:
                logger.info("任务被取消，循环终止。")
                break
            except Exception as e:
                logger.error(f"主循环发生未知错误: {e}", exc_info=True)
    
    async def _analyze_markets(self):
        """分析所有配置的交易对"""
        decisions = {}
        for symbol in config.TRADING_PAIRS:
            try:
                # 1. 获取所有时间框架的原始数据
                data_dict_raw = await self.data_fetcher.get_all_timeframes_data(symbol)
                
                if not data_dict_raw:
                    logger.warning(f"[{symbol}] 数据获取不完整，跳过本轮分析。")
                    continue

                # 2. 为所有数据计算指标
                data_dict_processed = self.indicator_calculator.calculate_indicators_for_all_timeframes(data_dict_raw)

                if not data_dict_processed:
                    logger.warning(f"[{symbol}] 指标计算失败，跳过本轮分析。")
                    continue
                
                # 3. 调用V2.1策略分析器进行决策
                decision = self.strategy_analyzer.analyze(symbol, data_dict_processed)
                decisions[symbol] = decision
                
                # 4. 显示分析结果
                await self._display_analysis_result(decision)

            except Exception as e:
                logger.error(f"分析交易对 {symbol} 时发生错误: {e}", exc_info=True)
                decisions[symbol] = {'decision': 'ERROR', 'reason': str(e)}

        # 5. 生成本轮分析报告
        await self._generate_analysis_report(decisions)
    
    async def _display_analysis_result(self, decision: Dict[str, Any]):
        """格式化并显示单个交易对的分析结果"""
        symbol = decision.get('symbol', 'UNKNOWN')
        action = decision.get('decision', 'WAIT')
        reason = decision.get('reason', 'N/A')
        details = decision.get('details', {})

        log_message = f"[{symbol}] 决策: {action:<8} | 原因: {reason}"
        
        if action == 'LONG':
            logger.success(log_message)
        elif action == 'SHORT':
            logger.error(log_message) # 使用红色突出做空信号
        elif action == 'WAIT':
            logger.info(log_message)
        elif action == 'ERROR':
            logger.warning(log_message)

        # 打印详细信息以便调试
        if details:
            trend_details = details.get('trend_details', {})
            
            # 安全地获取和格式化数值
            price = trend_details.get('price')
            ema_fast = trend_details.get('ema_fast')
            ema_slow = trend_details.get('ema_slow')
            
            price_str = f"{price:.4f}" if price is not None else "N/A"
            ema_fast_str = f"{ema_fast:.4f}" if ema_fast is not None else "N/A"
            ema_slow_str = f"{ema_slow:.4f}" if ema_slow is not None else "N/A"

            logger.debug(f"  - 2H趋势: {details.get('2h_trend')}, 价格: {price_str}, EMA10: {ema_fast_str}, EMA20: {ema_slow_str}")

            if 'effective_support_name' in details:
                level = details.get('effective_support_level')
                level_str = f"{level:.4f}" if level is not None else "N/A"
                logger.info(f"  - 有效支撑: {details['effective_support_name']} at {level_str}")

            if 'effective_resistance_name' in details:
                level = details.get('effective_resistance_level')
                level_str = f"{level:.4f}" if level is not None else "N/A"
                logger.info(f"  - 有效阻力: {details['effective_resistance_name']} at {level_str}")

            if 'trigger_candle_time' in details:
                logger.debug(f"  - 触发信号K线时间: {details['trigger_candle_time']}")
    
    async def _execute_trading_decision(self, decision: Dict[str, Any]):
        """执行交易决策（目前仅记录日志）"""
        # 注意：这里暂时只记录日志，不执行实际交易
        # 实际交易需要实现币安事件合约的相关API调用
        
        action = decision.get('decision')
        symbol = decision.get('symbol')
        
        if action in ['LONG', 'SHORT']:
            logger.info(f"📝 模拟交易: 对 {symbol} 执行 {action} 操作。")
            logger.info("   注意: 当前为模拟模式，未执行实际交易。")
            
            # 这里可以添加实际的交易执行代码
            # 例如：币安事件合约下单、风险管理等
    
    async def _generate_analysis_report(self, decisions: Dict[str, Any]):
        """生成分析报告"""
        try:
            logger.info("-" * 50)
            logger.info("📋 本轮分析报告")
            logger.info("-" * 50)
            
            # 统计各类决策
            stats = {
                'LONG': 0,
                'SHORT': 0,
                'LONG_WEAK': 0,
                'SHORT_WEAK': 0,
                'WAIT': 0,
                'ERROR': 0
            }
            
            for decision in decisions.values():
                action = decision.get('decision', 'UNKNOWN')
                if action in stats:
                    stats[action] += 1
            
            # 显示统计信息
            logger.info(f"强做多信号: {stats['LONG']} | 强做空信号: {stats['SHORT']}")
            logger.info(f"弱做多信号: {stats['LONG_WEAK']} | 弱做空信号: {stats['SHORT_WEAK']}")
            logger.info(f"观望: {stats['WAIT']} | 错误: {stats['ERROR']}")
            
            # 显示活跃信号
            active_signals = [
                f"{symbol}: {decision['decision']}" 
                for symbol, decision in decisions.items() 
                if decision.get('decision') not in ['WAIT', 'ERROR']
            ]
            
            if active_signals:
                logger.info("🎯 活跃交易信号:")
                for signal in active_signals:
                    text_b = {'text': f'bbbbbb <at user_id="618514145">丁光辉</at>'}
                    json_b = {'msg_type': 'text', 'content': text_b}
                    requests.post('https://open.feishu.cn/open-apis/bot/v2/hook/c8905c57-0d68-4366-93eb-df219b8794ad',
                                  headers={
                                      'Content-Type': 'application/json'
                                  }
                                  , data=json.dumps(json_b))
                    logger.info(f"   • {signal}")
            else:
                logger.info("🔇 当前无活跃交易信号")
            
            logger.info("-" * 50)
            
        except Exception as e:
            logger.error(f"生成分析报告时发生错误: {e}")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，准备退出...")
        self.is_running = False
    
    async def _cleanup(self):
        """清理资源"""
        try:
            logger.info("正在清理资源...")
            
            # 关闭数据获取器连接
            await self.data_fetcher.close()
            
            logger.info("资源清理完成")
            logger.info("=== BinanceEventTrader 已停止 ===")
            
        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}")


async def main():
    """主函数"""
    trader = BinanceEventTrader()
    
    try:
        # 初始化
        if not await trader.initialize():
            logger.error("初始化失败，程序退出")
            return
        
        # 设置信号处理器，用于接收Ctrl+C等中断信号
        signal.signal(signal.SIGINT, trader._signal_handler)
        signal.signal(signal.SIGTERM, trader._signal_handler)

        # 打开主循环的"引擎开关"
        trader.is_running = True
        
        # 显示启动信息
        logger.info("=== 币安事件合约交易机器人启动 ===")
        logger.info(f"策略版本: V2.1 - 双向对称规则")
        logger.info("提示: 当前为分析模式，不执行实际交易")
        logger.info("按 Ctrl+C 停止程序")
        logger.info("=" * 60)
        
        # 运行主循环
        await trader.run()
        
    except Exception as e:
        logger.error(f"程序运行时发生致命错误: {e}", exc_info=True)
    finally:
        logger.info("程序正在退出，执行清理操作...")
        await trader._cleanup()


if __name__ == "__main__":
    try:
        # 运行异步主函数
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        sys.exit(1) 