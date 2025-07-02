import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.markup import escape
import datetime
from typing import Dict, Any, List

from .api import NgaClient
from .ui import display_topic_details, display_topics
from . import config
from .exceptions import UserWantsToExit

def start_interactive_mode(console: Console, client: NgaClient, settings: Dict[str, Any]):
    """交互模式的主入口，使用 inquirer 实现菜单选择。"""
    while True:
        forums = config.get_forums()
        if not forums:
            console.print("[bold red]错误: 你还没有添加任何收藏的板块。[/]")
            console.print("请使用 `nga config` 命令添加一个板块。")
            return

        forum_list = list(forums.items())
        
        choices = [(f"{name} (fid: {fid})", fid) for name, fid in forum_list]
        choices.append(("退出程序", "exit"))

        questions = [
            inquirer.List('choice',
                          message="请使用方向键选择要浏览的板块，回车确认",
                          choices=choices,
                          carousel=True)
        ]
        
        try:
            answer = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        except KeyboardInterrupt:
            raise UserWantsToExit()

        if not answer or answer['choice'] == 'exit':
            raise UserWantsToExit()
        
        selected_fid = answer['choice']
        selected_name = next((name for name, fid in forum_list if fid == selected_fid), f"fid:{selected_fid}")
        
        browse_forum(console, client, selected_fid, selected_name, settings)

def browse_forum(console: Console, client: NgaClient, fid: int, forum_name: str, settings: Dict[str, Any]):
    """
    浏览指定板块的交互式循环。
    使用 rich.Table 显示帖子列表，并接收用户输入进行导航。
    """
    page = 1
    while True:
        console.rule(f"[bold]正在浏览: {forum_name} - 第 {page} 页[/]")
        with console.status("[bold cyan]正在获取帖子列表...[/]"):
            topics_data = client.get_topics(fid, page)

        if topics_data is None:
            console.print("[red]获取帖子列表失败。[/]")
            console.input("按回车键返回...")
            break

        actual_data = topics_data[0] if isinstance(topics_data, list) and topics_data else topics_data
        if not isinstance(actual_data, dict):
            console.print(f"[red]错误: 帖子列表数据格式无效。[/]")
            console.input("按回车键返回...")
            break

        # 使用 ui.display_topics 显示表格并获取帖子列表
        sorted_topics = display_topics(console, actual_data, page)

        if not sorted_topics:
            console.print("[yellow]该页没有帖子。[/yellow]")
            page = max(1, page - 1) # 如果当前页为空，则返回上一页
            console.input("按回车键继续...")
            continue
            
        prompt = f"\n[bold]输入帖子序号查看, (n)下一页, (p)上一页, (b)返回 > [/]"
        action = console.input(prompt).lower().strip()

        if action in ('b', 'q'):
            break
        elif action == 'n':
            page += 1
        elif action == 'p':
            if page > 1:
                page -= 1
            else:
                console.print("[yellow]已经是第一页了。[/yellow]")
                console.input("按回车键继续...")
        else:
            try:
                idx = int(action) - 1
                if 0 <= idx < len(sorted_topics):
                    tid = sorted_topics[idx]['tid']
                    view_topic(console, client, tid, settings)
                else:
                    console.print(f"[red]无效的序号: {action}[/red]")
                    console.input("按回车键继续...")
            except (ValueError, IndexError):
                console.print(f"[red]无效的输入: {action}[/red]")
                console.input("按回车键继续...")


def view_topic(console: Console, client: NgaClient, tid: int, settings: Dict[str, Any]):
    """阅读指定帖子内容的交互式循环。"""
    page = 1
    total_pages = 1

    console.rule(f"[bold]阅读帖子 (TID: {tid}) - 第 {page} 页[/]")
    with console.status("[bold cyan]正在加载帖子内容...[/]"):
        details = client.get_topic_details(tid, page)

    if details is None:
        console.log("[yellow]无法获取帖子详情。[/yellow]")
        return

    total_posts = details.get('__ROWS', 0)
    if total_posts == 0 and '__T' in details:
        total_posts = details['__T'].get('replies', 0) + 1
        
    rows_per_page = details.get('__R__ROWS_PAGE', 20) or 20
    total_pages = (total_posts + rows_per_page - 1) // rows_per_page if total_posts > 0 else 1
    
    display_topic_details(console, details, page, total_pages, settings)

    while True:
        prompt = f"\n[bold](p)上一页, (n)下一页, (b)返回, (exit)退出 [第 {page}/{total_pages} 页] > [/]"
        action = console.input(prompt).lower()

        if action == 'exit':
            raise UserWantsToExit()
            
        new_page = page
        if action == 'p':
            new_page = max(1, page - 1)
        elif action == 'n':
            new_page = min(total_pages, page + 1)
        elif action in ('b', 'q'):
            break
        else:
            console.print("[red]无效输入。[/]")
            continue
            
        if new_page == page:
            if action == 'p': console.print("[yellow]已经是第一页了。[/yellow]")
            elif action == 'n': console.print("[yellow]已经是最后一页了。[/yellow]")
            continue
            
        page = new_page

        console.rule(f"[bold]阅读帖子 (TID: {tid}) - 第 {page} 页[/]")
        with console.status("[bold cyan]正在加载帖子内容...[/]"):
            details = client.get_topic_details(tid, page)
        
        if details:
            display_topic_details(console, details, page, total_pages, settings)
        else:
            console.log("[yellow]无法获取该页的帖子详情。[/yellow]")
            if action == 'n': page -= 1
            if action == 'p': page += 1
