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
        发送请求并处理响应。
        使用更鲁棒的解码方式，优先尝试默认解码（UTF-8），失败则回退到 GBK。
        """
        url = f"{self.BASE_URL}{endpoint}"
        self._save_request_log(method, url, params, self.headers)

        try:
            response = self.client.request(method, url, params=params if method == 'GET' else None,
                                           data=params if method == 'POST' else None)
            response.raise_for_status()

            raw_bytes = response.content
            raw_text = ""

            # --- 核心修改点：更可靠的解码逻辑 ---
            try:
                # 1. 直接用 utf-8 解码 bytes
                raw_text = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # 2. 如果 utf-8 失败，说明是 gbk，用 gbk 解码
                raw_text = raw_bytes.decode('gbk', errors='replace')

            # 清理某些接口返回的 JSONP 包装
            if raw_text.startswith('window.script_muti_get_var_store='):
                raw_text = raw_text[len('window.script_muti_get_var_store='):-1]

            data = json.loads(raw_text, strict=False)

            # 保存最终成功解析的响应内容
            with open(config.LAST_RESPONSE_PATH, 'w', encoding='utf-8') as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))

            if "error" in data and data["error"]:
                error_msg = data['error'][0] if isinstance(data['error'], list) and data['error'] else data['error']
                console.print(Panel(f"[bold red]API 错误:[/bold red] {error_msg}", border_style="red"))
                return None

            # 返回 data 字段，如果不存在则返回整个解析后的字典
            return data.get("data", data)

        except (httpx.RequestError, json.JSONDecodeError, Exception) as e:
            self._save_error_log(url, e, params)
            console.print(Panel(f"[bold red]请求或解析时发生错误:[/bold red] {e}", border_style="red"))
            return None

    def verify_login(self) -> Optional[Dict[str, Any]]:
        """通过访问一个需要登录的页面来验证cookie有效性。"""
        if not self.headers.get('Cookie'):
            return None
        verify_url = f"{self.BASE_URL}/thread.php?fid=-7"
        try:
            # 使用 GBK 解码
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
