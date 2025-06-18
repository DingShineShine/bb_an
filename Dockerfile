# 使用官方的、轻量级的Python 3.10镜像作为基础
FROM python:3.10-slim-buster

# 设置环境变量，确保Python输出是无缓冲的，便于实时查看日志
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 设置工作目录
WORKDIR /app

# 复制依赖文件
# 我们先只复制这个文件并安装依赖，这样可以利用Docker的缓存机制。
# 只要requirements.txt没变，下次构建时就不需要重新安装，速度更快。
COPY requirements.txt .

# 安装依赖
# --no-cache-dir 选项可以减小镜像体积
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目中的所有文件到工作目录
COPY . .

# 容器启动时要执行的命令
# 我们运行start.py，它包含了环境检查等友好的启动流程
CMD ["python", "start.py"] 