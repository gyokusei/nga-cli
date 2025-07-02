import click
import os 
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from . import config
from .api import NgaClient
from .exceptions import UserWantsToExit

# 全局 console 实例
_console = None

def get_console_instance() -> Console:
    """根据配置创建或返回全局 Console 实例。"""
    global _console
    if _console is None:
        settings = config.get_settings()
        use_rich_style = settings.get("rich_style", True)
        _console = Console(no_color=not use_rich_style)
    return _console

def get_client() -> NgaClient:
    """创建并返回 NgaClient 实例。"""
    settings = config.get_settings()
    proxies = settings.get("proxies", {})
    if proxies.get('http'): os.environ['HTTP_PROXY'] = proxies['http']
    if proxies.get('https'): os.environ['HTTPS_PROXY'] = proxies['https']
    
    cookie_string = config.get_cookie_string()
    return NgaClient(cookie_string)


@click.group(invoke_without_command=True)
@click.version_option("0.0.1", "-v", "--version", message="%(prog)s v%(version)s - Interactive Config & Shell Completion Update")
@click.pass_context
def main_cli(ctx):
    """NGA 命令行浏览器"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(start)

@main_cli.command()
def start():
    """启动 NGA-CLI。"""
    console = get_console_instance()
    
    try:
        console.print(Panel(" NGA 命令行浏览器 v0.0.1 ", style="bold blue on white", expand=False))
        
        client = get_client()
        if not client.headers.get('Cookie'):
            console.print(Panel("[bold red]错误: 未找到 Cookie。[/]\n请先使用 `nga config` 命令配置。", title="需要配置", border_style="red"))
            return

        with console.status("[bold cyan]正在验证登录状态...[/]"):
            user_info = client.verify_login()

        if not user_info:
            console.print(Panel("[bold red]登录验证失败！请检查Cookie或网络。[/]", border_style="red"))
            console.print("提示: 可运行 `nga debug last-response` 查看服务器响应。")
            return
            
        console.print(Panel(f"欢迎回来, [bold green]{user_info.get('username', '未知用户')}[/]!", border_style="green"))
        
        settings = config.get_settings()
        mode = settings.get('mode', 'shell')

        if mode == 'shell':
            from .shell import start_shell_mode
            start_shell_mode(console, client, settings)
        else:
            from .interactive import start_interactive_mode
            start_interactive_mode(console, client, settings)
            
    except UserWantsToExit:
        console.print("\n[yellow]已退出程序。[/yellow]")


@main_cli.command()
def config_cmd():
    """进入交互式菜单来修改程序配置。"""
    console = get_console_instance()
    client = get_client()
    config.interactive_config_menu(client)

main_cli.add_command(config_cmd, "config")


@main_cli.group()
def debug():
    """用于调试的工具。"""
    pass

@debug.command(name="last-request")
def last_request():
    """查看最近一次API请求的参数和头信息。"""
    console = get_console_instance()
    try:
        with open(config.REQUEST_LOG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        parsed_json = json.loads(content)
        syntax = Syntax(json.dumps(parsed_json, indent=2, ensure_ascii=False), "json", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="最近一次网络请求"))
    except FileNotFoundError:
        console.print("[yellow]未找到最近的网络请求记录。[/yellow]")
    except (json.JSONDecodeError, Exception) as e:
        console.print(f"[red]打开或解析请求日志文件时出错: {e}[/red]")

@debug.command(name="last-response")
def last_response():
    """查看最近一次API请求的原始响应。"""
    console = get_console_instance()
    try:
        with open(config.LAST_RESPONSE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        try:
            parsed_json = json.loads(content)
            syntax = Syntax(json.dumps(parsed_json, indent=2, ensure_ascii=False), "json", theme="monokai", line_numbers=True)
        except json.JSONDecodeError:
            syntax = Syntax(content, "html", theme="monokai", line_numbers=True)

        console.print(Panel(syntax, title="最近一次网络响应"))
    except FileNotFoundError:
        console.print("[yellow]未找到最近的网络响应记录。[/]")
    except Exception as e:
        console.print(f"[red]打开日志文件时出错: {e}[/red]")


if __name__ == '__main__':
    main_cli()
