#!/bin/bash

# ==============================================================================
# nga-cli 一键安装脚本
#
# 使用方法:
#   curl -fsSL https://raw.githubusercontent.com/gyokusei/nga-cli/main/install.sh | bash
#   或者
#   wget -O - https://raw.githubusercontent.com/gyokusei/nga-cli/main/install.sh | bash
#
# 该脚本会执行以下操作:
#   1. 检查 git, python3, 和 pip3 是否已安装。
#   2. 检查 Python 版本是否 >= 3.8。
#   3. 从 GitHub 克隆最新的 `nga-cli` 仓库。
#   4. 使用 `pip` 安装此工具及其所有依赖。
#   5. 清理下载的源码。
#   6. 显示安装成功信息和使用提示。
# ==============================================================================

# --- 配置 ---
# 设置脚本在遇到错误时立即退出
set -e
# GitHub 仓库地址 (请确保这是你的仓库地址)
REPO_URL="https://github.com/gyokusei/nga-cli.git"
# 项目名称
REPO_NAME="nga-cli"
# Python 最低版本要求
MIN_PYTHON_VERSION="3.8"

# --- 颜色定义 (用于美化输出) ---
COLOR_RESET='\033[0m'
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[0;33m'

# --- 辅助函数 ---
info_msg() {
    echo -e "${COLOR_YELLOW}[INFO] $1${COLOR_RESET}"
}

success_msg() {
    echo -e "${COLOR_GREEN}[SUCCESS] $1${COLOR_RESET}"
}

error_msg() {
    echo -e "${COLOR_RED}[ERROR] $1${COLOR_RESET}"
}

# --- 主逻辑 ---

# 1. 检查系统依赖
check_dependencies() {
    info_msg "开始检查系统环境和依赖..."
    
    # 检查核心命令
    for cmd in git python3 pip3; do
        if ! command -v "$cmd" &> /dev/null; then
            error_msg "必需命令 '$cmd' 未找到。请先安装它。"
            exit 1
        fi
    done

    # 检查 Python 版本
    installed_version=$(python3 --version 2>&1 | awk '{print $2}')
    if ! printf '%s\n%s\n' "$MIN_PYTHON_VERSION" "$installed_version" | sort -V -C; then
        error_msg "Python 版本过低。需要 v$MIN_PYTHON_VERSION 或更高版本，但检测到 v$installed_version。"
        error_msg "请升级你的 Python 版本。"
        exit 1
    fi

    success_msg "环境检查通过！"
}

# 2. 克隆并安装
clone_and_install() {
    # 清理可能存在的旧目录
    if [ -d "$REPO_NAME" ]; then
        info_msg "发现旧的 '$REPO_NAME' 目录，正在清理..."
        rm -rf "$REPO_NAME"
    fi

    # 克隆仓库
    info_msg "正在从 GitHub 克隆仓库..."
    git clone --depth 1 "$REPO_URL" "$REPO_NAME" || {
        error_msg "克隆仓库失败。请检查网络连接或仓库地址是否正确。"
        exit 1
    }

    cd "$REPO_NAME"

    # 使用 pip 安装
    info_msg "正在安装 nga-cli 及其依赖..."
    python3 -m pip install . || {
        error_msg "使用 pip 安装失败。请检查 pip 是否工作正常。"
        # 在退出前返回到上级目录，以便后续清理
        cd ..
        exit 1
    }
    
    success_msg "依赖安装完成！"
}

# 3. 清理工作
cleanup() {
    info_msg "正在清理安装文件..."
    cd ..
    rm -rf "$REPO_NAME"
    success_msg "清理完成！"
}

# 4. 显示最终信息
final_message() {
    echo
    success_msg "🎉 nga-cli 已成功安装！ 🎉"
    info_msg "现在你可以开始使用了。"
    info_msg "1. 首先，运行配置向导来设置你的 Cookie 和收藏板块:"
    echo -e "   ${COLOR_GREEN}nga config${COLOR_RESET}"
    info_msg "2. 配置完成后，直接运行以下命令启动程序:"
    echo -e "   ${COLOR_GREEN}nga${COLOR_RESET} 或 ${COLOR_GREEN}nga start${COLOR_RESET}"
    echo
    info_msg "如果系统提示 'command not found: nga'，这可能是因为 ~/.local/bin 不在你的 PATH 环境变量中。"
    info_msg "请将下面这行命令添加到你的 shell 配置文件中 (例如 ~/.bashrc 或 ~/.zshrc):"
    echo -e "   ${COLOR_YELLOW}export PATH=\"\$HOME/.local/bin:\$PATH\"${COLOR_RESET}"
    info_msg "添加后，请重启你的终端或运行 'source ~/.bashrc' (或对应的文件) 来使配置生效。"
}


# --- 脚本执行入口 ---
main() {
    check_dependencies
    clone_and_install
    cleanup
    final_message
}

# 启动主函数
main
