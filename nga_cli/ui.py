import re
import html
import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markup import escape
from rich.padding import Padding


def parse_nga_content(content: str) -> Text:
    """
    将 NGA 的 BBCode 语法更完整地解析为 rich 的 Text 对象。
    """
    if not isinstance(content, str):
        return Text("内容格式错误", style="bold red")

    text = html.unescape(content)
    text = text.replace('<br/>', '\n').replace('<br>', '\n')
    text = re.sub(r'\[s:ac:(\w+)]', r':\1:', text)
    text = re.sub(r'\[s:a2:(\w+)]', r':\1:', text)
    text = re.sub(r'\[s:(\w+)]', r':\1:', text)

    def replace_quote(m):
        quote_content = m.group(1).strip()
        processed_quote = escape(re.sub(r'\[.*?\]', '', quote_content))
        return f"\n[on default] [b]引用:[/b] \n > {processed_quote} [/on default]\n"

    text = re.sub(r'\[quote\](.*?)\[/quote\]', replace_quote, text, flags=re.DOTALL | re.IGNORECASE)

    def replace_collapse(m):
        title = m.group(1) or "点击显示/隐藏"
        collapse_content = m.group(2).strip()
        processed_content = escape(re.sub(r'\[.*?\]', '', collapse_content))
        return f"\n[on default] [b]折叠内容: {escape(title)}[/b] \n > {processed_content} [/on default]\n"

    text = re.sub(r'\[collapse(?:=(.*?))?\](.*?)\[/collapse\]', replace_collapse, text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r'\[b\](.*?)\[/b\]', r'[b]\1[/b]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[i\](.*?)\[/i\]', r'[i]\1[/i]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[u\](.*?)\[/u\]', r'[u]\1[/u]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[del\](.*?)\[/del\]', r'[s]\1[/s]', text, flags=re.IGNORECASE)

    text = re.sub(r'\[img\]\./(.*?)\[/img\]', r'[link=https://img.nga.178.com/\1](图片链接)[/link]', text,
                  flags=re.IGNORECASE)
    text = re.sub(r'\[url\](.*?)\[/url\]', r'[link=\1](\1)[/link]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', r'[link=\1]\2[/link]', text, flags=re.IGNORECASE)

    text = re.sub(r'\[/?(color|size|font|align|list|td|tr|table|pid|tid|.*?)\]', '', text, flags=re.IGNORECASE)

    return Text.from_markup(text)


def display_topics(console: Console, topics_data: Dict[str, Any], page: int) -> Optional[List[Dict]]:
    """显示帖子列表，并返回帖子列表用于后续选择。"""

    title = f"帖子列表 (第 {page} 页)"

    table = Table(title=title, expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("标题", style="cyan", no_wrap=False)
    table.add_column("作者", style="green", width=20)
    table.add_column("回复", justify="right", style="magenta", width=6)
    table.add_column("发布时间", style="yellow", width=18)

    topics_raw = topics_data.get('__T')
    topic_list = []

    if isinstance(topics_raw, dict):
        topic_list = list(topics_raw.values())
    elif isinstance(topics_raw, list):
        topic_list = topics_raw
    else:
        # 如果没有帖子，直接返回空列表
        return []

    sorted_topics = sorted(topic_list, key=lambda x: int(x.get('lastpost', 0)), reverse=True)

    for i, topic in enumerate(sorted_topics, 1):
        # --- 核心修改点 ---
        # 强制将 subject 转换为字符串，以防 API 返回 bool 类型或其他非字符串类型
        title_text = escape(str(topic.get('subject', '无标题')))
        author = escape(topic.get('author', '未知'))
        replies = str(topic.get('replies', 0))

        post_timestamp = topic.get('postdate', 0)
        post_time_str = datetime.datetime.fromtimestamp(post_timestamp).strftime(
            '%Y-%m-%d %H:%M') if post_timestamp else '未知时间'

        if 'b' in topic.get('titlefont', ''): title_text = f"[bold]{title_text}[/bold]"
        if 'color' in topic.get('titlefont', ''): title_text = f"[yellow]{title_text}[/yellow]"

        table.add_row(str(i), title_text, author, replies, post_time_str)

    console.print(table)
    return sorted_topics


def display_topic_details(console: Console, details: Dict[str, Any], page: int, total_pages: int,
                          settings: Dict[str, Any]):
    """显示帖子详情和回复。"""
    topic_info = details.get('__T', {})
    replies = details.get('__R', [])
    users = details.get('__U', {})

    title = topic_info.get('subject', '无标题')
    console.print(Panel(f"[bold cyan]{escape(title)}[/] (第 {page}/{total_pages} 页)", border_style="green"))

    if not isinstance(users, dict):
        console.print("[red]用户信息格式错误。[/red]")
        return

    if isinstance(replies, dict):
        sorted_replies = sorted(replies.values(), key=lambda item: int(item.get('lou', 0)))
    elif isinstance(replies, list):
        sorted_replies = sorted(replies, key=lambda item: int(item.get('lou', 0)))
    else:
        console.print("[red]回复数据格式错误。[/red]")
        return

    for reply in sorted_replies:
        author_id = str(reply.get('authorid'))
        author_info = users.get(author_id, {})

        author_name = author_info.get('username', '未知用户')

        post_timestamp = reply.get('postdatetimestamp', 0)
        if post_timestamp and isinstance(post_timestamp, int):
            post_date = datetime.datetime.fromtimestamp(post_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        else:
            post_date = reply.get('postdate', '')  # Fallback to the pre-formatted string

        lou = reply.get('lou', 'N/A')

        signature_panel = None
        if settings.get("show_signatures", True):
            signature_raw = author_info.get('signature', '')
            if signature_raw:
                signature_content = parse_nga_content(signature_raw)
                if signature_content.plain.strip():
                    signature_panel = Panel(signature_content, title="签名", border_style="dim", expand=False)

        lou_text = f"#{lou}"
        if lou == 0: lou_text = "[bold yellow]楼主[/bold yellow]"

        meta_info = f"[bold cyan]{escape(author_name)}[/] [dim]({post_date})[/]"
        content_text = parse_nga_content(reply.get('content', ''))

        reply_table = Table.grid(expand=True, padding=(0, 1))
        reply_table.add_column(ratio=1)
        reply_table.add_column(justify="right")
        reply_table.add_row(meta_info, lou_text)

        console.print(Panel(reply_table, border_style="blue" if lou != 0 else "yellow", padding=(0, 1)))

        console.print(Padding(content_text, (0, 4)))

        if signature_panel:
            console.print(signature_panel)
        console.print()