#!/usr/bin/env bash
set -e

echo "=== top10tool 一键安装 ==="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 未安装，请先安装 Python 3.10+"
    exit 1
fi

echo "Python 已检测到: $(python3 --version)"
echo ""

# 安装依赖
echo "[1/2] 安装 Python 依赖..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
pip3 install -r "$SCRIPT_DIR/requirements.txt" -q
echo "      依赖安装完成"
echo ""

# 创建 /usr/local/bin/top10tool 包装脚本
echo "[2/2] 创建 top10tool 命令..."
WRAPPER="/usr/local/bin/top10tool"

sudo tee "$WRAPPER" > /dev/null << EOF
#!/usr/bin/env bash
cd "$SCRIPT_DIR" && python3 cli.py "\$@"
EOF

sudo chmod +x "$WRAPPER"

echo "      命令已安装到 $WRAPPER"
echo ""
echo "=== 安装完成! ==="
echo ""
echo "现在在任意终端输入 top10tool 即可启动。"
echo "首次运行会引导你配置 LLM（API 地址、Key、模型）。"
