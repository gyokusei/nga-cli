import os
import json
import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .api import NgaClient

console = Console()

# --- 路径定义 ---
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "nga-cli")
COOKIE_PATH = os.path.join(CONFIG_DIR, "cookies.json")
FORUMS_PATH = os.path.join(CONFIG_DIR, "forums.json")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
LOG_FILE_PATH = os.path.join(CONFIG_DIR, "nga-cli.log")
LAST_RESPONSE_PATH = os.path.join(CONFIG_DIR, "last_response.txt")
REQUEST_LOG_PATH = os.path.join(CONFIG_DIR, "last_request.json")
SHELL_HISTORY_PATH = os.path.join(CONFIG_DIR, "shell_history.txt")


# --- 默认配置 ---
DEFAULT_FORUMS = {

}
DEFAULT_SETTINGS = {
    "proxies": {"http": None, "https": None},
    "show_signatures": False,
    "mode": "interactive",
    "rich_style": True,
}

# --- 核心辅助函数 ---
def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def _load_json(path: str, default: Any = None) -> Any:
    ensure_config_dir()
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default

def _save_json(path: str, data: Any) -> bool:
    ensure_config_dir()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        console.print(f"[red]错误: 无法写入文件 {path}。原因: {e}[/red]")
        return False

# --- Cookie 管理 ---
def get_cookie_string() -> str:
    cookies = _load_json(COOKIE_PATH, {})
    return "; ".join([f"{k}={v}" for k, v in cookies.items()])

def _parse_cookie_string_for_validation(cookie_string: str) -> Dict[str, str]:
    try:
        cookies = dict(item.strip().split("=", 1) for item in cookie_string.split(";"))
        if "ngaPassportUid" in cookies and "ngaPassportCid" in cookies:
            return cookies
    except ValueError:
        pass
    return {}

def save_cookies_from_string(cookie_string: str) -> bool:
    cookies = _parse_cookie_string_for_validation(cookie_string)
    if not cookies:
        console.print("[red]错误: Cookie 格式不正确。必须包含 'ngaPassportUid' 和 'ngaPassportCid'。[/red]")
        return False
    return _save_json(COOKIE_PATH, cookies)

# --- 板块管理 ---
def get_forums() -> Dict[str, int]:
    return _load_json(FORUMS_PATH, DEFAULT_FORUMS)

def save_forums(forums: Dict[str, int]) -> bool:
    return _save_json(FORUMS_PATH, forums)

# --- 设置管理 ---
def get_settings() -> Dict[str, Any]:
    settings = _load_json(SETTINGS_PATH, {})
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)
    return settings

def save_settings(settings: Dict[str, Any]) -> bool:
    return _save_json(SETTINGS_PATH, settings)

# --- 新的交互式配置菜单 ---

def _config_cookie():
    """交互式配置Cookie。"""
    console.print(Panel("[bold]请输入您的 NGA Cookie[/]\n\n1. 登录 [link=https://bbs.nga.cn]NGA 网站[/link]\n2. 打开浏览器开发者工具 (F12)\n3. 找到任意一个对 `bbs.nga.cn` 的请求\n4. 在请求头中找到 'Cookie' 项，并复制其完整值。", title="如何获取 Cookie", border_style="yellow"))
    cookie_string = console.input("[bold]Cookie > [/bold] ")
    if save_cookies_from_string(cookie_string):
        console.print("[green]Cookie 已成功保存。[/green]")
    console.input("\n按回车键返回菜单...")

def _config_forums(client: 'NgaClient'):
    """交互式管理收藏板块。"""
    while True:
        console.clear()
        console.print(Panel("[bold]管理收藏板块[/]", border_style="blue", expand=False))
        forums = get_forums()
        
        table = Table(title="当前收藏")
        table.add_column("名称", style="cyan")
        table.add_column("板块ID (fid)", style="magenta", justify="right")
        for name, fid in forums.items():
            table.add_row(name, str(fid))
        console.print(table)
        
        questions = [
            inquirer.List('action',
                          message="请选择操作",
                          choices=['添加新板块', '删除一个板块', '返回主菜单'],
                          carousel=True)
        ]
        answer = inquirer.prompt(questions)
        if not answer or answer['action'] == '返回主菜单':
            break

        if answer['action'] == '添加新板块':
            fid_str = console.input("[bold]请输入要添加板块的 fid > [/bold]")
            try:
                fid = int(fid_str)
                with console.status(f"[cyan]正在查询 fid: {fid} 的板块信息...[/]"):
                    details = client.get_forum_details(fid)
                
                if details and details.get('__F') and 'name' in details['__F']:
                    forum_name = details['__F']['name']
                    console.print(f"查询成功！板块名称为: [bold green]{forum_name}[/]")
                    confirm = inquirer.prompt([inquirer.Confirm('add', message=f"是否确认添加板块 '{forum_name}'?", default=True)])
                    if confirm and confirm['add']:
                        forums[forum_name] = fid
                        save_forums(forums)
                        console.print(f"[green]板块 '{forum_name}' 已添加！[/green]")
                else:
                    console.print("[red]查询失败！未找到该 fid 对应的板块，或API返回格式有误。[/red]")
            except ValueError:
                console.print("[red]输入无效，fid 必须是数字。[/red]")
            console.input("\n按回车键继续...")

        elif answer['action'] == '删除一个板块':
            if not forums:
                console.print("[yellow]当前没有收藏的板块可供删除。[/yellow]")
                console.input("\n按回车键继续...")
                continue
            
            forum_to_remove = inquirer.prompt([
                inquirer.List('name', message="请选择要删除的板块", choices=list(forums.keys()))
            ])
            if forum_to_remove:
                name = forum_to_remove['name']
                confirm = inquirer.prompt([inquirer.Confirm('delete', message=f"是否确认删除板块 '{name}'?", default=False)])
                if confirm and confirm['delete']:
                    del forums[name]
                    save_forums(forums)
                    console.print(f"[green]板块 '{name}' 已删除。[/green]")
            console.input("\n按回车键继续...")


def _config_proxies():
    """交互式配置代理。"""
    settings = get_settings()
    proxies = settings.get('proxies', {})
    
    console.print(Panel("[bold]配置网络代理[/]", border_style="blue", expand=False))
    console.print("提示：如果想保留当前值，请直接按回车键。如果想清空，请输入 'none'。")
    
    current_http = proxies.get('http') or "未设置"
    http_proxy_input = console.input(f"[bold]HTTP 代理 (当前: {current_http}) > [/bold]")
    
    current_https = proxies.get('https') or "未设置"
    https_proxy_input = console.input(f"[bold]HTTPS 代理 (当前: {current_https}) > [/bold]")

    # 根据用户输入决定最终值
    if http_proxy_input == '':
        final_http_proxy = proxies.get('http')
    elif http_proxy_input.lower() == 'none':
        final_http_proxy = None
    else:
        final_http_proxy = http_proxy_input

    if https_proxy_input == '':
        final_https_proxy = proxies.get('https')
    elif https_proxy_input.lower() == 'none':
        final_https_proxy = None
    else:
        final_https_proxy = https_proxy_input

    settings['proxies'] = {
        'http': final_http_proxy,
        'https': final_https_proxy
    }
    save_settings(settings)
    console.print("[green]代理设置已保存。[/green]")
    console.input("\n按回车键返回菜单...")

def _config_general():
    """交互式配置通用选项。"""
    settings = get_settings()
    questions = [
        inquirer.List('mode', message="选择默认启动模式", choices=['shell', 'interactive'], default=settings.get('mode'), carousel=True),
        inquirer.Confirm('show_signatures', message="是否显示用户签名?", default=settings.get('show_signatures')),
        inquirer.Confirm('rich_style', message="是否启用彩色/富文本样式 (摸鱼模式请选 '否')?", default=settings.get('rich_style')),
    ]
    answers = inquirer.prompt(questions)
    if answers:
        settings.update(answers)
        save_settings(settings)
        console.print("[green]通用设置已保存。[/green]")
    else:
        console.print("[yellow]未做任何修改。[/yellow]")
    console.input("\n按回车键返回菜单...")


def display_current_config():
    """显示所有当前配置。"""
    console.clear()
    console.print(Panel("[bold]NGA-CLI 当前配置总览[/]", border_style="blue", expand=False))
    
    # Cookie 状态
    cookie_string = get_cookie_string()
    if cookie_string and _parse_cookie_string_for_validation(cookie_string):
        console.print(f"  [green]✓[/] Cookie: 已配置")
    else:
        console.print("  [red]✗[/] Cookie: 未配置或格式不正确")

    # 通用设置
    settings = get_settings()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column()
    table.add_column()
    table.add_row("默认模式:", f"[cyan]{settings.get('mode')}[/]")
    table.add_row("显示签名:", f"[cyan]{'是' if settings.get('show_signatures') else '否'}[/]")
    table.add_row("富文本样式:", f"[cyan]{'启用' if settings.get('rich_style') else '禁用 (摸鱼模式)'}[/]")
    table.add_row("HTTP 代理:", f"[cyan]{settings.get('proxies', {}).get('http') or '未设置'}[/]")
    table.add_row("HTTPS 代理:", f"[cyan]{settings.get('proxies', {}).get('https') or '未设置'}[/]")
    console.print(Panel(table, title="通用设置"))

    # 收藏板块
    forums = get_forums()
    forums_table = Table(box=None, padding=(0, 2))
    forums_table.add_column("板块名称", style="cyan")
    forums_table.add_column("FID", style="magenta", justify="right")
    for name, fid in forums.items():
        forums_table.add_row(name, str(fid))
    console.print(Panel(forums_table, title="收藏的板块"))
    
    console.input("\n按回车键返回菜单...")

def interactive_config_menu(client: 'NgaClient'):
    """
    启动交互式配置主菜单。
    """
    while True:
        console.clear()
        console.print(Panel(" NGA-CLI 配置中心 ", style="bold blue on white", expand=False))
        
        questions = [
            inquirer.List(
                'choice',
                message="请选择要配置的项目",
                choices=[
                    '设置 Cookie',
                    '管理收藏板块',
                    '配置网络代理',
                    '通用选项设置',
                    '查看当前所有配置',
                    '退出配置'
                ],
                carousel=True
            )
        ]
        
        answer = inquirer.prompt(questions)
        
        if not answer or answer['choice'] == '退出配置':
            console.print("[yellow]已退出配置。[/yellow]")
            break
        
        choice = answer['choice']
        console.clear()

        if choice == '设置 Cookie':
            _config_cookie()
        elif choice == '管理收藏板块':
            _config_forums(client)
        elif choice == '配置网络代理':
            _config_proxies()
        elif choice == '通用选项设置':
            _config_general()
        elif choice == '查看当前所有配置':
            display_current_config()
