"""
BinanceEventTrader 主程序
币安事件合约自动化交易机器人
实现"顺大势，逆小势"的多时间框架交易策略
"""
import asyncio
import signal
import sys
from datetime import datetime
from typing import Dict, Any
from loguru import logger

# 导入项目模块
from config.config import config, system_params
from core.data_fetcher import data_fetcher
from core.strategy_analyzer import strategy_analyzer


class BinanceEventTrader:
    """币安事件合约交易机器人主类"""
    
    def __init__(self):
        """初始化交易机器人"""
        self.is_running = False
        self.trading_enabled = False  # 初期设为False，仅进行分析和日志记录
        self._setup_logging()
        
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
        
        logger.info("日志系统初始化完成")
    
    async def initialize(self) -> bool:
        """初始化交易机器人"""
        try:
            logger.info("=== BinanceEventTrader 初始化开始 ===")
            
            # 1. 验证配置
            if not config.validate_config():
                logger.error("配置验证失败！请检查API密钥配置")
                return False
            
            logger.info(f"配置验证通过 (测试模式: {config.USE_TESTNET})")
            
            # 2. 初始化数据获取器
            if not await data_fetcher.initialize():
                logger.error("数据获取器初始化失败")
                return False
            
            logger.info("数据获取器初始化成功")
            
            # 3. 显示交易对信息
            logger.info(f"监控交易对: {config.TRADING_PAIRS}")
            logger.info(f"时间框架: 大周期({config.MAJOR_TIMEFRAME}) | 小周期({config.MINOR_TIMEFRAME})")
            
            # 4. 显示策略参数
            logger.info("=== 策略参数 ===")
            logger.info(f"EMA周期: 快线({config.IndicatorParams.EMA_FAST}) | 慢线({config.IndicatorParams.EMA_SLOW})")
            logger.info(f"RSI周期: {config.IndicatorParams.RSI_PERIOD}")
            logger.info(f"背离检测回看周期: {config.IndicatorParams.DIVERGENCE_LOOKBACK}")
            
            logger.info("=== 初始化完成 ===")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
    
    async def run(self):
        """运行主循环"""
        try:
            self.is_running = True
            logger.info("=== 开始运行交易机器人 ===")
            
            # 设置信号处理器
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            while self.is_running:
                try:
                    # 执行一轮分析
                    await self._analyze_markets()
                    
                    # 等待下一轮分析
                    logger.debug(f"等待 {system_params.DATA_UPDATE_INTERVAL} 秒进行下一轮分析...")
                    await asyncio.sleep(system_params.DATA_UPDATE_INTERVAL)
                    
                except KeyboardInterrupt:
                    logger.info("收到中断信号，正在停止...")
                    break
                except Exception as e:
                    logger.error(f"主循环执行错误: {e}")
                    await asyncio.sleep(5)  # 短暂等待后重试
            
        except Exception as e:
            logger.error(f"运行时发生致命错误: {e}")
        finally:
            await self._cleanup()
    
    async def _analyze_markets(self):
        """分析所有市场并生成交易决策"""
        try:
            logger.info("=" * 50)
            logger.info(f"🔍 开始新一轮市场分析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 50)
            
            # 1. 获取所有交易对的数据
            all_market_data = await data_fetcher.get_all_pairs_data()
            
            if not all_market_data:
                logger.warning("未能获取市场数据，跳过本轮分析")
                return
            
            # 2. 分析每个交易对
            decisions = {}
            for symbol, (data_2h, data_5m) in all_market_data.items():
                try:
                    # 执行策略分析
                    decision = strategy_analyzer.analyze(symbol, data_2h, data_5m)
                    decisions[symbol] = decision
                    
                    # 显示分析结果
                    await self._display_analysis_result(decision)
                    
                    # 如果启用交易，执行交易决策（目前仅记录日志）
                    if self.trading_enabled:
                        await self._execute_trading_decision(decision)
                    
                except Exception as e:
                    logger.error(f"分析 {symbol} 时发生错误: {e}")
                    continue
            
            # 3. 生成分析报告
            await self._generate_analysis_report(decisions)
            
        except Exception as e:
            logger.error(f"市场分析过程中发生错误: {e}")
    
    async def _display_analysis_result(self, decision: Dict[str, Any]):
        """显示分析结果"""
        try:
            symbol = decision.get('symbol', 'UNKNOWN')
            action = decision.get('decision', 'UNKNOWN')
            confidence = decision.get('confidence', 0.0)
            reason = decision.get('reason', '无原因')
            
            # 根据决策类型使用不同的显示格式
            if action == 'LONG':
                logger.success(f"🚀 {symbol}: 【做多信号】置信度: {confidence:.2%} | {reason}")
                self._display_signal_details(decision, "📈 做多")
                
            elif action == 'SHORT':
                logger.success(f"🔻 {symbol}: 【做空信号】置信度: {confidence:.2%} | {reason}")
                self._display_signal_details(decision, "📉 做空")
                
            elif action in ['LONG_WEAK', 'SHORT_WEAK']:
                action_type = "弱做多" if 'LONG' in action else "弱做空"
                logger.warning(f"⚠️ {symbol}: 【{action_type}信号】置信度: {confidence:.2%} | {reason}")
                
            elif action == 'WAIT':
                logger.info(f"⏳ {symbol}: 【观望】{reason}")
                
            elif action == 'ERROR':
                logger.error(f"❌ {symbol}: 【分析错误】{reason}")
                
            else:
                logger.info(f"❓ {symbol}: 【未知状态】{action} | {reason}")
            
        except Exception as e:
            logger.error(f"显示分析结果时发生错误: {e}")
    
    def _display_signal_details(self, decision: Dict[str, Any], signal_type: str):
        """显示信号详细信息"""
        try:
            major_trend = decision.get('major_trend', {})
            minor_signals = decision.get('minor_signals', {})
            recommended_action = decision.get('recommended_action', {})
            
            logger.info(f"   {signal_type}信号详情:")
            
            # 大周期趋势信息
            trend_direction = major_trend.get('direction', 'UNKNOWN')
            trend_strength = major_trend.get('strength', 0.0)
            logger.info(f"   📊 大周期趋势: {trend_direction} (强度: {trend_strength:.2%})")
            
            # RSI背离信息
            rsi_divergence = minor_signals.get('rsi_divergence', {})
            if rsi_divergence.get('bullish_divergence') or rsi_divergence.get('bearish_divergence'):
                div_type = "看涨" if rsi_divergence.get('bullish_divergence') else "看跌"
                div_strength = rsi_divergence.get('divergence_strength', 0.0)
                logger.info(f"   🎯 RSI背离: {div_type}背离 (强度: {div_strength:.2%})")
            
            # 满足的条件
            conditions_met = recommended_action.get('conditions_met', [])
            if conditions_met:
                logger.info(f"   ✅ 满足条件: {', '.join(conditions_met)}")
            
            # 当前价格信息
            current_state = minor_signals.get('current_state', {})
            if current_state:
                price = current_state.get('price', 0)
                rsi = current_state.get('rsi', 0)
                logger.info(f"   💰 当前价格: {price} | RSI: {rsi:.1f}")
                
        except Exception as e:
            logger.error(f"显示信号详情时发生错误: {e}")
    
    async def _execute_trading_decision(self, decision: Dict[str, Any]):
        """执行交易决策（目前仅记录日志）"""
        # 注意：这里暂时只记录日志，不执行实际交易
        # 实际交易需要实现币安事件合约的相关API调用
        
        action = decision.get('decision')
        symbol = decision.get('symbol')
        confidence = decision.get('confidence', 0.0)
        
        if action in ['LONG', 'SHORT']:
            logger.info(f"📝 交易日志: {symbol} - {action} (置信度: {confidence:.2%})")
            logger.info("   注意: 当前为模拟模式，未执行实际交易")
            
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
            await data_fetcher.close()
            
            logger.info("资源清理完成")
            logger.info("=== BinanceEventTrader 已停止 ===")
            
        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}")


async def main():
    """主函数"""
    try:
        # 创建交易机器人实例
        trader = BinanceEventTrader()
        
        # 初始化
        if not await trader.initialize():
            logger.error("初始化失败，程序退出")
            return
        
        # 显示启动信息
        logger.info("=== 币安事件合约交易机器人启动 ===")
        logger.info("策略: 顺大势，逆小势 - 多时间框架RSI背离策略")
        logger.info("提示: 当前为分析模式，不执行实际交易")
        logger.info("按 Ctrl+C 停止程序")
        logger.info("=" * 60)
        
        # 运行主循环
        await trader.run()
        
    except Exception as e:
        logger.error(f"程序运行时发生致命错误: {e}")
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    try:
        # 运行异步主函数
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        sys.exit(1) 