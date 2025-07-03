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
from rich import box


def parse_nga_content(content: str) -> Text:
    """
    将 NGA 的 BBCode 语法更完整地解析为 rich 的 Text 对象。
    这是一个重构后的安全版本。
    """
    if not isinstance(content, str):
        return Text("内容格式错误", style="bold red")

    # 1. 初始清理
    text = html.unescape(content)
    text = text.replace('<br/>', '\n').replace('<br>', '\n')

    # 2. 处理复杂标签，如 [quote] 和 [collapse]，确保内部内容被转义
    def replace_quote(m):
        # 只转义 BBCode 标签内的内容
        quote_content = m.group(1).strip()
        # 递归地解析引用内部的内容
        processed_quote = parse_nga_content(quote_content).plain
        return f"\n[on default][b]引用:[/b]\n> {escape(processed_quote)}[/on default]\n"

    text = re.sub(r'\[quote\](.*?)\[/quote\]', replace_quote, text, flags=re.DOTALL | re.IGNORECASE)

    def replace_collapse(m):
        title = escape(m.group(1) or "点击显示/隐藏")
        collapse_content = m.group(2).strip()
        processed_content = parse_nga_content(collapse_content).plain
        return f"\n[on default][b]折叠内容: {title}[/b]\n> {escape(processed_content)}[/on default]\n"

    text = re.sub(r'\[collapse(?:=(.*?))?\](.*?)\[/collapse\]', replace_collapse, text, flags=re.DOTALL | re.IGNORECASE)

    # 3. 替换样式和链接标签
    text = re.sub(r'\[b\](.*?)\[/b\]', r'[b]\1[/b]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[i\](.*?)\[/i\]', r'[i]\1[/i]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[u\](.*?)\[/u\]', r'[u]\1[/u]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[del\](.*?)\[/del\]', r'[s]\1[/s]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[color=(.*?)\](.*?)\[/color\]', r'[\1]\2[/\1]', text, flags=re.IGNORECASE)

    text = re.sub(r'\[img\]\./(.*?)\[/img\]', r'[link=https://img.nga.178.com/\1](图片链接)[/link]', text,
                  flags=re.IGNORECASE)
    text = re.sub(r'\[url\](.*?)\[/url\]', r'[link=\1](\1)[/link]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', r'[link=\1]\2[/link]', text, flags=re.IGNORECASE)

    # 4. 清理所有未处理的标签
    text = re.sub(
        r'\[/?(size|font|align|list|li|td|tr|table|pid|tid|topic|post|attach|flash|audio|video|style|code|reply|email|floor|comment|customachieve|achievement|album|item|spell|wowicon|wowitem|wowspell|wowquest|wowachievement|wowcurrency|wowfaction|wowtitle|wowcard|hsicon|hscard|hscardgold|d3icon|d3item|sc2icon|owicon|woticon|ff14item|ff14action|ff14status|ff14quest|ff14duty|ff14achieve|ff14recipe|ff14map|ff14mob|ff14npc|ff14weather|ff14instance|ff14title|ff14emote|ff14fashion|ff14fish|ff14gc|ff14mount|ff14minion|ff14orchestrion|ff14tripletriad|ff14lore|ff14character|ff14leve|ff14fate|ff14node|ff14shop|ff14areanpc|ff14areamob|ff14areazone|ff14areamap|ff14areafate|ff14areanode|ff14areashop)(?:=[^\]]*)?\]',
        '', text, flags=re.IGNORECASE)

    # 5. 替换简单表情
    text = re.sub(r'\[s:ac:(\w+)]', r':\1:', text, flags=re.IGNORECASE)
    text = re.sub(r'\[s:a2:(\w+)]', r':\1:', text, flags=re.IGNORECASE)
    text = re.sub(r'\[s:(\w+)]', r':\1:', text, flags=re.IGNORECASE)

    # 直接从处理后的文本创建，不再使用 escape
    return Text.from_markup(text, emoji=True)


def display_topics(console: Console, topics_data: Dict[str, Any], page: int) -> Optional[List[Dict]]:
    """显示帖子列表，并返回帖子列表用于后续选择。"""

    title = f"帖子列表 (第 {page} 页)"

    table = Table(title=title, expand=True, title_justify="center", header_style="bold magenta", box=box.HEAVY_HEAD)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("标题", style="cyan", no_wrap=False, ratio=50)
    table.add_column("作者", style="green", no_wrap=True, ratio=25)
    table.add_column("回复", justify="right", style="magenta", no_wrap=True, ratio=10)
    table.add_column("发布时间", style="yellow", no_wrap=True, ratio=15)

    topics_raw = topics_data.get('__T')
    topic_list = []

    if isinstance(topics_raw, dict):
        topic_list = list(topics_raw.values())
    elif isinstance(topics_raw, list):
        topic_list = topics_raw
    else:
        return []

    for topic in topic_list:
        if 'lastpost' not in topic or not str(topic.get('lastpost')).isdigit():
            topic['lastpost'] = topic.get('postdate', 0)

    sorted_topics = sorted(topic_list, key=lambda x: int(x.get('lastpost', 0)), reverse=True)

    for i, topic in enumerate(sorted_topics, 1):
        # --- 修复：使用 `or` 来处理 API 可能返回 null 的情况 ---
        title_text = escape(topic.get('subject') or '无标题')
        author = escape(topic.get('author') or '未知')
        replies = str(topic.get('replies', 0))

        post_timestamp = topic.get('postdate', 0)
        post_time_str = datetime.datetime.fromtimestamp(int(post_timestamp)).strftime(
            '%Y-%m-%d %H:%M:%S') if str(post_timestamp).isdigit() and int(post_timestamp) > 0 else '未知时间'

        if 'b' in topic.get('titlefont', ''): title_text = f"[bold]{title_text}[/bold]"

        color_match = re.search(r'color:([^;"]+)', str(topic.get('titlefont')))
        if color_match:
            color = color_match.group(1).strip().lower()
            if color in ['red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'white', 'black']:
                title_text = f"[{color}]{title_text}[/{color}]"

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
    console.print(
        Panel(f"[bold cyan]{escape(title)}[/] (第 {page}/{total_pages} 页)", border_style="green", title_align="left"))

    if not isinstance(users, dict):
        console.print("[red]用户信息格式错误。[/red]")
        return

    # 确保 replies 是列表
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

        # --- 修复：同样使用 or 处理可能为 null 的 username ---
        author_name = str(author_info.get('username') or '未知用户')

        post_timestamp = reply.get('postdatetimestamp', 0)
        if post_timestamp and str(post_timestamp).isdigit():
            post_date = datetime.datetime.fromtimestamp(int(post_timestamp)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            post_date = reply.get('postdate', '')

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
