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
# —— 保存仓库路径，供自动更新使用 ——
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.top10tool"
mkdir -p "$CONFIG_DIR"
echo "$REPO_DIR" > "$CONFIG_DIR/repo_path"

echo "  正在安装 top10tool ..."
echo ""

"$PYTHON" -m pip install "$REPO_DIR/." --quiet

# —— 保存已安装版本，供自动更新比对 ——
git -C "$REPO_DIR" rev-parse origin/master > "$CONFIG_DIR/installed_commit" 2>/dev/null || true

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
