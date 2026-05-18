#!/bin/bash
# 胶片伴侣 AI — 启动脚本
# 从当前环境继承 API Key 并启动 Web 服务

cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
export PYTHONUNBUFFERED=1

# 从父环境继承 API Key（Hermes 终端已设好）
# 如果 .env 文件存在则加载
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

PORT=${1:-8080}
python3 main.py --port "$PORT"
