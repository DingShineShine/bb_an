# BinanceEventTrader 币安事件合约交易机器人

## 项目简介

BinanceEventTrader 是一个专为币安事件合约设计的自动化交易机器人，实现了"顺大势，逆小势"的多时间框架交易策略。该机器人通过分析不同时间周期的技术指标，特别是RSI背离信号，来识别高概率的交易机会。

## 核心特性

- 🚀 **多时间框架分析**: 结合2小时和5分钟时间框架的技术分析
- 📊 **RSI背离检测**: 专业的背离信号识别算法
- 🎯 **智能交易策略**: "顺大势，逆小势" - 跟随主要趋势，逆转短期波动
- 💰 **风险管理**: 内置止损止盈和资金管理功能
- 📈 **实时监控**: 持续监控ETHUSDT和BTCUSDT市场
- 🔄 **异步架构**: 高性能的异步数据处理和分析

## 交易策略说明

### 核心理念：顺大势，逆小势

1. **大周期趋势判断 (2小时)**:
   - 使用EMA快慢线判断主要趋势方向
   - 确认趋势强度和可持续性

2. **小周期入场时机 (5分钟)**:
   - 寻找RSI背离信号作为入场点
   - 结合价格形态确认反转机会

3. **信号确认条件**:
   - 大周期趋势明确（多头/空头）
   - 小周期出现相应的RSI背离
   - 满足最小信号强度要求

## 项目结构

```
BinanceEventTrader/
├── config/
│   └── config.py              # 配置文件
├── core/
│   ├── data_fetcher.py        # 数据获取模块
│   ├── indicator_calculator.py # 技术指标计算
│   └── strategy_analyzer.py   # 策略分析引擎
├── logs/                      # 日志文件目录
├── main.py                    # 主程序入口
├── requirements.txt           # 依赖包列表
├── .env.example              # 环境变量示例
├── .gitignore               # Git忽略文件
└── README.md                # 项目说明文档
```

## 安装指南

### 1. 环境要求

- Python 3.8+
- 币安API账户（建议先使用测试网）

### 2. 安装步骤

```bash
# 克隆项目（如果使用Git）
git clone <repository-url>
cd BinanceEventTrader

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入您的API密钥
```

### 3. 配置API密钥

1. 访问 [币安测试网](https://testnet.binance.vision/) 创建测试账户
2. 获取API密钥和Secret密钥
3. 编辑 `.env` 文件，填入您的密钥信息

```env
BINANCE_TESTNET_API_KEY=your_testnet_api_key_here
BINANCE_TESTNET_SECRET_KEY=your_testnet_secret_key_here
USE_TESTNET=true
```

## 使用方法

### 1. 启动程序

```bash
python main.py
```

### 2. 程序功能

- **实时市场分析**: 自动获取和分析ETHUSDT、BTCUSDT的K线数据
- **信号生成**: 根据策略生成买入/卖出信号
- **详细日志**: 完整的分析过程和决策记录
- **风险提示**: 当前版本仅进行分析，不执行实际交易

### 3. 停止程序

按 `Ctrl+C` 安全停止程序

## 配置说明

### 主要参数

- **交易对**: 默认监控 ETHUSDT, BTCUSDT
- **时间框架**: 大周期2小时，小周期5分钟
- **EMA参数**: 快线12周期，慢线26周期
- **RSI参数**: 14周期，背离检测回看50周期
- **更新频率**: 默认60秒检查一次

### 自定义配置

编辑 `config/config.py` 文件来调整策略参数：

```python
# 示例：修改EMA参数
IndicatorParams.EMA_FAST = 10
IndicatorParams.EMA_SLOW = 20

# 示例：修改RSI参数
IndicatorParams.RSI_PERIOD = 21
```

## 注意事项

⚠️ **重要提醒**:

1. **测试优先**: 请务必先在测试网上测试程序功能
2. **风险管理**: 开始实盘前，请充分了解交易风险
3. **资金安全**: 建议使用专门的交易子账户，限制API权限
4. **持续监控**: 程序需要您的持续监控和维护
5. **策略调整**: 根据市场情况适时调整策略参数

## 技术支持

如有问题或建议，请查看：

- 日志文件: `logs/` 目录下的详细日志
- 配置检查: 确保 `.env` 文件正确配置
- 网络连接: 确保网络连接稳定
- API限制: 注意币安API的请求频率限制

## 免责声明

本项目仅供学习和研究使用。cryptocurrency交易存在极高风险，可能导致全部资金损失。使用本软件进行交易的所有风险由用户自行承担。开发者不对任何交易损失承担责任。

## 许可证

本项目仅供个人学习和研究使用，不得用于商业用途。 