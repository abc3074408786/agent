#!/bin/bash
# Agent Desktop 构建脚本

set -e

echo "🔨 Agent Desktop Build Script"
echo "=============================="

# 检查参数
MODE=${1:-"lite"}

if [ "$MODE" != "full" ] && [ "$MODE" != "lite" ]; then
  echo "用法: ./scripts/build.sh [full|lite]"
  echo "  full - 完整版 (捆绑 Python 环境)"
  echo "  lite - 精简版 (需要用户自装 Python)"
  exit 1
fi

echo "📦 构建模式: $MODE"
echo ""

# 安装依赖
echo "📥 安装依赖..."
npm install

# 构建前端
echo "🏗️  构建前端..."
npx tsc
npx vite build

# 如果是完整版，准备 Python 环境
if [ "$MODE" = "full" ]; then
  echo "🐍 准备 Python 嵌入式环境..."
  
  PYTHON_DIR="python-embedded"
  
  if [ ! -d "$PYTHON_DIR" ]; then
    echo "⚠️  请先下载 Python 嵌入式版本到 $PYTHON_DIR 目录"
    echo ""
    echo "下载地址:"
    echo "  Windows: https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
    echo "  macOS/Linux: 建议使用 python-build-standalone"
    echo "    https://github.com/indygreg/python-build-standalone/releases"
    echo ""
    echo "下载后解压到 $PYTHON_DIR/ 目录，然后重新运行此脚本"
    exit 1
  fi

  # 安装 Agent 依赖到嵌入式 Python
  echo "📦 安装 Agent Python 依赖..."
  $PYTHON_DIR/python -m pip install -r ../agent/requirements.txt --target $PYTHON_DIR/Lib/site-packages 2>/dev/null || true
fi

# 打包 Electron
echo "📦 打包 Electron 应用..."
if [ "$MODE" = "full" ]; then
  npx electron-builder --config electron-builder.full.yml
else
  npx electron-builder --config electron-builder.lite.yml
fi

echo ""
echo "✅ 构建完成！输出目录: release/"
echo ""
ls -la release/ 2>/dev/null || echo "(release 目录为空或不存在)"
