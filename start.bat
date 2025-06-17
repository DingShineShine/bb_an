@echo off
chcp 65001 >nul 2>&1
title BinanceEventTrader - 币安事件合约交易机器人

echo ============================================================
echo 🚀 BinanceEventTrader - 币安事件合约交易机器人
echo ============================================================
echo 交易策略: 顺大势，逆小势 (多时间框架RSI背离策略)
echo Python 3.12 兼容版本
echo ============================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python版本检查:
python --version

REM 检查是否在conda环境中
if defined CONDA_DEFAULT_ENV (
    echo ✅ 当前conda环境: %CONDA_DEFAULT_ENV%
) else (
    echo ⚠️  建议使用conda环境运行
)

REM 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo ✅ 发现虚拟环境，正在激活...
    call venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    echo ✅ 发现虚拟环境，正在激活...
    call env\Scripts\activate.bat
) else (
    echo ⚠️  未发现虚拟环境，建议创建虚拟环境:
    echo    python -m venv venv
    echo    或使用conda: conda create -n bb_an python=3.12
)

REM 检查requirements.txt
if not exist "requirements.txt" (
    echo ❌ 错误: 未找到requirements.txt文件
    pause
    exit /b 1
)

echo.
echo 🔧 正在检查依赖包...
pip install -r requirements.txt --quiet

echo.
echo 🚀 正在启动 BinanceEventTrader...
echo ============================================================

REM 运行主程序
python start.py

echo.
echo ============================================================
echo 程序已结束运行
pause 