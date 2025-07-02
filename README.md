# NGA-CLI: 命令行里的 NGA 论坛浏览器

一个在终端里舒适浏览 NGA 论坛的命令行工具。

## ✨ 主要特性

* **两种浏览模式**: Shell 模式 (类似 bash，支持 `Tab` 补全) 和传统的交互模式。
* **摸鱼模式**: 支持禁用所有彩色样式，完美融入工作环境。
* **调试友好**: 记录请求和响应，方便定位问题。

## 📦 安装

### 一键安装 (推荐: macOS / Linux)

在你的终端里运行以下命令：

```bash
/bin/bash -c "$(curl -fsSL [https://raw.githubusercontent.com/gyokusei/nga-cli/main/scripts/install.sh](https://raw.githubusercontent.com/gyokusei/nga-cli/main/scripts/install.sh))"
````

### 手动安装

1.  确保你已经安装了 Python 3.8 或更高版本。
2.  克隆本仓库到本地：
    ```bash
    git clone [https://github.com/gyokusei/nga-cli.git](https://github.com/gyokusei/nga-cli.git)
    cd nga-cli
    ```
3.  通过 pip 安装项目及其依赖：
    ```bash
    pip install .
    ```

## 🚀 快速开始

1.  **首次配置**: 安装后，**必须**先配置 Cookie。运行 `nga config`，选择 `设置 Cookie` 并按提示操作。
    > Cookie 是你的登录凭证，将仅保存在本地，请妥善保管。
2.  **开始浏览**: 配置完成后，直接运行 `nga` 即可启动。

## 📖 使用指南

### 交互模式(默认)

1.  **选择板块**: 使用 `↑` 和 `↓` 方向键选择板块，按 `Enter` 键进入。
2.  **浏览帖子**: 输入帖子**序号**并按 `Enter` 查看。
3.  **导航**: 输入 `n` (下一页), `p` (上一页), 或 `b` (返回) 进行导航。

### Shell 模式

如果你在配置中将默认模式设为 `shell`，程序将以此模式启动。

  * `ls`: 列出收藏的板块或当前板块的帖子。
  * `cd <fid>`: 进入指定 `fid` 的板块 (也支持按名称进入)。`cd ..` 返回。
  * `cat <序号>`: 查看 `ls` 列表中对应序号的帖子。
  * `p` / `n`: 上一页 / 下一页。
  * `exit` / `q`: 退出程序。
  * `help`: 显示帮助信息。

> **提示**: 在 Shell 模式下，可以随时使用 `Tab` 键进行命令和参数的自动补全，使用 `↑` 和 `↓` 箭头可以翻阅历史命令。

### 配置 (`nga config`)

运行 `nga config` 进入交互式菜单，可以管理所有设置，包括：

  * **设置 Cookie** (必须)
  * **管理收藏板块** (输入 `fid` 自动获取名称)
  * **配置网络代理**
  * **通用选项设置**:
      * 默认启动模式 (`shell` 或 `interactive`)
      * 是否显示签名
      * 是否启用彩色样式 (摸鱼模式)


## 🙏 致谢

本项目在开发过程中，参考了 [DarrenIce/NGA-MoFish](https://github.com/DarrenIce/NGA-MoFish) 项目的部分思路，在此表示感谢。

## 调试 (`nga debug`)

当程序出错或显示不正常时，可以用此命令查看最近一次请求以及从 NGA 服务器收到的原始数据，方便定位问题。

```bash
nga debug last-request
nga debug last-response
```

## 📄 许可证

本项目采用 [MIT License](https://opensource.org/licenses/MIT) 授权。
