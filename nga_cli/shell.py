import shlex
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing import Dict, Any, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style

from .api import NgaClient
from .ui import display_topics, display_topic_details
from . import config
from .exceptions import UserWantsToExit

# --- Tab补全实现 ---
class NgaShellCompleter(Completer):
    """为NGA Shell提供上下文感知的自动补全。"""
    def __init__(self, shell_instance: 'NgaShell'):
        self.shell = shell_instance
        self.commands = ['ls', 'cd', 'cat', 'p', 'n', 'help', 'exit', 'q']

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = document.text.split()

        # 如果在输入第一个词
        if len(words) == 0 or (len(words) == 1 and not document.text.endswith(' ')):
            for cmd in self.commands:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
            return

        # 为 'cd' 命令提供 fid 补全
        if len(words) > 1 and words[0] == 'cd':
            forums = config.get_forums()
            arg_text = words[-1] if len(words) > 1 else ''
            if not document.text.endswith(' '):
                 for name, fid in forums.items():
                    if str(fid).startswith(arg_text):
                        yield Completion(str(fid), start_position=-len(arg_text), display=f"{fid} ({name})")
            
        # 为 'cat' 命令提供参数补全
        elif len(words) > 1 and words[0] == 'cat':
            arg_text = words[-1] if len(words) > 1 else ''
            if self.shell.topics_cache and not document.text.endswith(' '):
                for i in range(1, len(self.shell.topics_cache) + 1):
                    if str(i).startswith(arg_text):
                        yield Completion(str(i), start_position=-len(arg_text))


def view_topic(console: Console, client: NgaClient, tid: int, settings: Dict[str, Any]):
    """
    在 Shell 模式下阅读指定帖子内容的交互式循环。
    修复了翻页逻辑。
    """
    page = 1
    total_pages = 1  # 先设置一个默认值

    # 步骤 1: 在循环外先加载第一页，目的是为了获取正确的总页数
    console.rule(f"[bold]阅读帖子 (TID: {tid}) - 第 {page} 页[/]")
    with console.status("[bold cyan]正在加载帖子内容...[/]"):
        details = client.get_topic_details(tid, page)

    if details is None:
        console.log("[yellow]无法获取帖子详情。[/yellow]")
        return

    # 步骤 2: 根据第一页返回的数据，计算一次总页数，并在之后复用这个值
    # 使用 __ROWS (总帖子数) 或 __T['replies'] + 1 来计算总数
    total_posts = details.get('__ROWS', 0)
    if total_posts == 0 and '__T' in details: # Fallback for some cases
        total_posts = details['__T'].get('replies', 0) + 1
        
    rows_per_page = details.get('__R__ROWS_PAGE', 20) or 20
    total_pages = (total_posts + rows_per_page - 1) // rows_per_page if total_posts > 0 else 1
    
    # 步骤 3: 显示第一页的内容
    display_topic_details(console, details, page, total_pages, settings)

    # 步骤 4: 进入交互循环，此时 total_pages 已经是固定的正确值
    while True:
        prompt = f"\n[bold](p)上一页, (n)下一页, (b)返回, (exit)退出程序 [第 {page}/{total_pages} 页] > [/]"
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

        # 如果页码没有变化，则不执行任何操作
        if new_page == page:
            if action == 'p':
                console.print("[yellow]已经是第一页了。[/yellow]")
            elif action == 'n':
                console.print("[yellow]已经是最后一页了。[/yellow]")
            continue
        
        page = new_page

        # 仅在页码实际改变时才重新获取数据和显示
        console.rule(f"[bold]阅读帖子 (TID: {tid}) - 第 {page} 页[/]")
        with console.status("[bold cyan]正在加载帖子内容...[/]"):
            details = client.get_topic_details(tid, page)
        
        if details:
            # 注意：从第二页开始，API可能不返回总页数信息，所以我们继续使用之前计算的 total_pages
            display_topic_details(console, details, page, total_pages, settings)
        else:
            console.log("[yellow]无法获取该页的帖子详情。[/yellow]")
            # 如果翻页失败，退回到上一页的状态
            if action == 'n': page -= 1
            if action == 'p': page += 1

class NgaShell:
    def __init__(self, console: Console, client: NgaClient, settings: Dict[str, Any]):
        self.console = console
        self.client = client
        self.settings = settings
        self.current_fid: Optional[int] = None
        self.current_fname: str = "~"
        self.current_page: int = 1
        self.topics_cache: List[Dict] = []
        
        rich_style_enabled = self.settings.get("rich_style", True)
        prompt_style = Style.from_dict({
            'prompt': 'cyan bold',
        }) if rich_style_enabled else None
        
        self.prompt_session = PromptSession(
            history=FileHistory(config.SHELL_HISTORY_PATH),
            style=prompt_style
        )
        self.completer = NgaShellCompleter(self)

    def run(self):
        """启动 shell 的主循环。"""
        self.console.print(Panel("欢迎来到 NGA 命令行模式。输入 `help` 查看可用命令，按 `Tab` 键可自动补全。", style="yellow"))
        while True:
            try:
                prompt_text = [
                    ('class:prompt', self.current_fname),
                    ('', '> ')
                ]
                
                cmd_line = self.prompt_session.prompt(
                    prompt_text,
                    completer=self.completer,
                    auto_suggest=AutoSuggestFromHistory()
                )

                if not cmd_line.strip():
                    continue
                
                parts = shlex.split(cmd_line)
                command = parts[0].lower()
                args = parts[1:]

                cmd_func = getattr(self, f"cmd_{command}", self.cmd_unknown)
                cmd_func(args)
            except UserWantsToExit:
                raise
            except (KeyboardInterrupt, EOFError):
                raise UserWantsToExit()
            except Exception as e:
                self.console.print(f"[bold red]发生错误: {e}[/]")
                import traceback
                traceback.print_exc()

    def cmd_unknown(self, args):
        self.console.print(f"[red]未知命令。输入 `help` 查看帮助。[/]")

    def cmd_help(self, args):
        self.console.print("""
[bold]可用命令:[/bold]
  [cyan]ls[/]                      - 列出收藏的板块或当前板块的帖子。
  [cyan]cd[/] [yellow]<fid>[/]            - 切换到指定板块 (支持Tab补全, 也可使用名称)。
                           使用 'cd ..' 返回根目录。
  [cyan]cat[/] [yellow]<index>[/]         - 查看指定序号的帖子详情 (支持Tab补全)。
  [cyan]p[/] / [cyan]n[/]                  - 翻页 (上一页/下一页)。
  [cyan]exit[/] / [cyan]q[/]               - 退出程序。
  [cyan]help[/]                  - 显示此帮助信息。
        """)

    def cmd_ls(self, args=None):
        """列出板块或帖子。行为取决于当前是否在板块内。"""
        if self.current_fid is None:
            forums = config.get_forums()
            self.console.print(Panel("收藏的板块", border_style="blue", expand=False))
            table = Table(show_header=False, box=None)
            table.add_column(style="magenta", width=10)
            table.add_column(style="cyan")
            for name, fid in forums.items():
                table.add_row(str(fid), name)
            self.console.print(table)
        else:
            self.console.rule(f"[bold]正在浏览: {self.current_fname} - 第 {self.current_page} 页[/]")
            with self.console.status("[cyan]获取帖子...[/]"):
                data = self.client.get_topics(self.current_fid, self.current_page)
            
            if not data:
                self.console.print("[red]获取帖子列表失败。[/]")
                if self.current_page > 1: self.current_page -= 1
                return

            actual_data = data[0] if isinstance(data, list) and data else data
            topics_raw = actual_data.get('__T')

            if not topics_raw and self.current_page > 1:
                self.console.print("[yellow]已经是最后一页了。[/yellow]")
                self.current_page -= 1
                return

            self.topics_cache = display_topics(self.console, actual_data, self.current_page)
            if not self.topics_cache:
                self.console.print("[yellow]该页没有帖子。[/yellow]")


    def cmd_cd(self, args):
        """切换目录到指定板块或返回上一级。"""
        if not args:
            self.console.print("[red]用法: cd <板块fid>[/]"); return
        
        target = args[0]
        
        if target == '..':
            self.current_fid = None
            self.current_fname = "~"
            self.current_page = 1
            self.topics_cache = []
            return

        forums = config.get_forums()
        found_fid = None
        
        try:
            target_fid = int(target)
            if target_fid in forums.values():
                found_fid = target_fid
                self.current_fname = next((name for name, fid in forums.items() if fid == target_fid), f"fid:{target_fid}")
        except ValueError:
            if target in forums:
                found_fid = forums[target]
                self.current_fname = target
        
        if found_fid is not None:
            self.current_fid = found_fid
            self.current_page = 1
            self.console.print(f"已进入板块: [cyan]{self.current_fname}[/]")
            self.cmd_ls()
        else:
            self.console.print(f"[red]错误: 在收藏夹中找不到板块 '{target}'。[/]")

    def cmd_cat(self, args):
        if not args:
            self.console.print("[red]用法: cat <帖子序号>[/]"); return
        if not self.topics_cache:
            self.console.print("[yellow]请先使用 `ls` 列出帖子。[/]"); return
            
        try:
            idx = int(args[0]) - 1
            if 0 <= idx < len(self.topics_cache):
                tid = self.topics_cache[idx]['tid']
                view_topic(self.console, self.client, tid, self.settings)
                # 从帖子返回后，重新渲染当前列表，以防有新回复等
                self.cmd_ls()
            else:
                self.console.print("[red]无效的帖子序号。[/]")
        except (ValueError, IndexError):
            self.console.print("[red]无效的帖子序号。[/]")

    def cmd_p(self, args):
        """翻到上一页"""
        if self.current_fid is None: self.console.print("[yellow]请先进入一个板块。[/]"); return
        if self.current_page > 1:
            self.current_page -= 1
            self.cmd_ls()
        else:
            self.console.print("[yellow]已经是第一页了。[/]")

    def cmd_n(self, args):
        """翻到下一页"""
        if self.current_fid is None: self.console.print("[yellow]请先进入一个板块。[/]"); return
        self.current_page += 1
        self.cmd_ls()

    def cmd_exit(self, args):
        raise UserWantsToExit()
    
    cmd_q = cmd_exit


def start_shell_mode(console: Console, client: NgaClient, settings: Dict[str, Any]):
    shell = NgaShell(console, client, settings)
    shell.run()
