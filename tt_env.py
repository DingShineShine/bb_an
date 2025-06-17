from dotenv import load_dotenv
import os

# 加载 .env 文件
load_dotenv()

# 获取环境变量
api_key = os.getenv("BINANCE_TESTNET_API_KEY")
secret_key = os.getenv("BINANCE_TESTNET_SECRET_KEY")

# 打印结果
print(f"API Key: {api_key}")
print(f"Secret Key: {secret_key}")

# 检查是否成功加载
if api_key and secret_key:
    print("Environment variables loaded successfully.")
else:
    print("Failed to load environment variables.")