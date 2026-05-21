#!/usr/bin/env bash
set -e

echo "=== top10tool 一键卸载 ==="
echo ""

# 1. 删除 /usr/local/bin/top10tool
if [ -f "/usr/local/bin/top10tool" ]; then
    sudo rm -f /usr/local/bin/top10tool
    echo "[OK] 已删除 /usr/local/bin/top10tool"
else
    echo "[--] /usr/local/bin/top10tool 不存在，跳过"
fi

# 2. 删除配置文件
CONFIG_DIR="$HOME/.top10tool"
if [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    echo "[OK] 已删除配置文件 $CONFIG_DIR"
else
    echo "[--] 配置文件不存在，跳过"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo "=== 卸载完成 ==="
echo "项目文件保留在 $SCRIPT_DIR"
echo "如需删除项目，手动执行: rm -rf $SCRIPT_DIR"
