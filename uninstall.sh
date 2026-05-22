#!/usr/bin/env bash
set -e

echo "=== top10tool 卸载 ==="
echo ""

# 1. 卸载 pip 包
echo "[1/2] 卸载 top10tool ..."
if python3 -m pip uninstall top10tool -y 2>/dev/null || python -m pip uninstall top10tool -y 2>/dev/null; then
    echo "      已卸载 top10tool"
else
    echo "      top10tool 未安装或已卸载"
fi

# 2. 删除配置文件
CONFIG_DIR="$HOME/.top10tool"
if [ -d "$CONFIG_DIR" ]; then
    echo "[2/2] 清理配置文件 ..."
    rm -rf "$CONFIG_DIR"
    echo "      已删除 $CONFIG_DIR"
else
    echo "[2/2] 配置文件不存在，跳过"
fi

echo ""
echo "=== 卸载完成 ==="
