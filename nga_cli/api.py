import httpx
import json
import logging
import re
import os
from typing import Dict, Any, Optional

from rich.console import Console
from rich.panel import Panel

from . import config

console = Console()

# --- 设置文件日志 ---
config.ensure_config_dir()
logging.basicConfig(
    filename=config.LOG_FILE_PATH,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


class NgaClient:
    """处理所有与 NGA API 的通信 (使用 httpx)。"""
    BASE_URL = "https://bbs.nga.cn"

    COMMON_HEADERS = {
        'User-Agent': 'NGA_WP_JW(;WINDOWS)',
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Referer": "https://bbs.nga.cn/"
    }

    def __init__(self, cookie_string: str):
        self.headers = self.COMMON_HEADERS.copy()
        if cookie_string:
            self.headers['Cookie'] = cookie_string

        # 代理设置由调用方 (cli.py) 通过设置环境变量来完成, httpx 会自动识别
        self.client = httpx.Client(headers=self.headers, timeout=20.0)

    def _save_request_log(self, method: str, url: str, params: Optional[Dict], headers: Dict):
        """保存请求日志，用于调试，会过滤掉Cookie。"""
        log_data = {
            "method": method,
            "url": url,
            "params": params,
            "headers": {k: v for k, v in headers.items() if k.lower() != 'cookie'}
        }
        with open(config.REQUEST_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=4, ensure_ascii=False)

    def _save_error_log(self, url: str, error: Exception, params: Optional[Dict] = None):
        """记录错误日志。"""
        error_message = f"请求失败\nURL: {url}\n"
        if params: error_message += f"参数: {params}\n"
        error_message += f"错误: {error!r}\n"
        logging.error(error_message)

    def _request(self, endpoint: str, params: Optional[Dict] = None, method: str = 'GET') -> Optional[Dict[str, Any]]:
        """
        发送请求并处理响应。增加了对响应内容类型和基本结构的验证。
        """
        url = f"{self.BASE_URL}{endpoint}"
        self._save_request_log(method, url, params, self.headers)

        raw_text = ""  # 在 try 块外部初始化
        try:
            response = self.client.request(method, url, params=params if method == 'GET' else None,
                                           data=params if method == 'POST' else None)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            if 'json' not in content_type:
                console.print(
                    Panel(f"[bold red]服务器返回了非预期的内容类型:[/bold red] {content_type}", border_style="red"))
                with open(config.LAST_RESPONSE_PATH, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                console.print("[yellow]原始响应已保存，请运行 `nga debug last-response` 查看。[/yellow]")
                return None

            raw_bytes = response.content
            try:
                raw_text = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                raw_text = raw_bytes.decode('gbk', errors='replace')

            if raw_text.startswith('window.script_muti_get_var_store='):
                raw_text = raw_text[len('window.script_muti_get_var_store='):-1]

            cleaned_text = raw_text.strip()

            if not cleaned_text:
                console.print(Panel("[bold yellow]服务器返回了空响应。[/bold yellow]", border_style="yellow"))
                return None

            # --- 核心修复 1：使用更健壮的正则来修复无效的转义 ---
            # 这会查找所有不属于合法JSON转义序列的单个反斜杠，并修复它们
            repaired_text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', cleaned_text)

            data = json.loads(repaired_text, strict=False)

            # 仅在成功时写入常规的响应日志
            with open(config.LAST_RESPONSE_PATH, 'w', encoding='utf-8') as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))

            if "error" in data and data["error"]:
                error_msg = data['error'][0] if isinstance(data['error'], list) and data['error'] else data['error']
                console.print(Panel(f"[bold red]API 错误:[/bold red] {error_msg}", border_style="red"))
                return None

            return data.get("data", data)

        except (json.JSONDecodeError, httpx.RequestError, Exception) as e:
            self._save_error_log(url, e, params)

            # --- 核心修复 2：将错误响应写入一个独立的、不会被覆盖的文件 ---
            # 这样就解决了用户指出的“日志被后续成功请求覆盖”的问题
            error_log_path = os.path.join(config.CONFIG_DIR, 'last_error_response.txt')
            with open(error_log_path, 'w', encoding='utf-8') as f:
                f.write(raw_text)  # 保存最原始的、导致错误的文本

            console.print(Panel(f"[bold red]请求或解析时发生错误:[/bold red] {e}", border_style="red"))
            if isinstance(e, json.JSONDecodeError):
                console.print(f"[dim]错误发生在第 {e.lineno} 行, 第 {e.colno} 列。[/dim]")

            console.print(
                f"[bold yellow]重要提示：[/bold yellow] 导致错误的原始响应已保存到下面的独立文件中，以防被后续请求覆盖：")
            console.print(f"[cyan]{error_log_path}[/cyan]")
            return None

    def verify_login(self) -> Optional[Dict[str, Any]]:
        """通过访问一个需要登录的页面来验证cookie有效性。"""
        if not self.headers.get('Cookie'):
            return None
        verify_url = f"{self.BASE_URL}/thread.php?fid=-7"
        try:
            response = self.client.get(verify_url)
            response.raise_for_status()
            html_content = response.content.decode('gbk', errors='ignore')

            with open(config.LAST_RESPONSE_PATH, 'w', encoding='utf-8') as f:
                f.write(html_content)

            u_match = re.search(r"window\.__U\s*=\s*(\{.*?\});", html_content)
            if u_match and u_match.group(1):
                user_info = json.loads(u_match.group(1))
                if user_info.get("uid"):
                    return user_info

            uname_match = re.search(r"__CURRENT_UNAME = '([^']*)',", html_content)
            if uname_match and uname_match.group(1):
                return {"username": uname_match.group(1)}

            return None
        except (httpx.RequestError, Exception) as e:
            self._save_error_log(verify_url, e)
            return None

    def get_forum_details(self, fid: int) -> Optional[Dict[str, Any]]:
        """根据fid获取板块的JSON数据，主要用于获取板块名称。"""
        params = {'fid': fid, '__output': 11}
        return self._request("/thread.php", params, method='GET')

    def get_topics(self, fid: int, page: int = 1) -> Optional[Dict[str, Any]]:
        """获取指定板块的帖子列表。"""
        params = {'fid': fid, 'page': page, '__output': 11}
        return self._request("/thread.php", params, method='GET')

    def get_topic_details(self, tid: int, page: int = 1) -> Optional[Dict[str, Any]]:
        """获取指定帖子的详细内容和回复。"""
        params = {'tid': tid, 'page': page, '__output': 11}
        return self._request("/read.php", params, method='GET')
