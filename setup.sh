#!/usr/bin/env bash
set -e

echo "================================================"
echo "   top10tool — 全局安装"
echo "================================================"
echo ""

# —— 检测 Python ——
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] 未检测到 Python 3.10+"
    exit 1
fi

echo "  Python: $("$PYTHON" --version 2>&1)"
echo ""
echo "  正在安装 top10tool ..."
echo ""

"$PYTHON" -m pip install "$(dirname "$0")/." --quiet

echo "================================================"
echo "   安装完成!"
echo "================================================"
echo ""
echo "  top10tool 已全局可用，在任意终端输入即可启动。"
echo "  首次运行会引导你配置 LLM 连接信息。"
echo ""
echo "  验证:"
echo "    which top10tool"
echo "    top10tool"
echo ""
