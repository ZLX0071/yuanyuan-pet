"""AI 服务接入（T4.1）：OpenAI 兼容 chat/completions，标准库实现、零新增依赖。

配置来自 data/config.json（gitignore，绝不进仓库）：
{"ai": {"base_url": …, "api_key": …, "model": …, "max_tokens": …, "monthly_token_budget": …}}

安全边界：base_url 只允许 http/https，且解析后的 IP 不得为环回/私网/链路本地/保留地址
（防 SSRF 指向本机与内网）；禁用重定向；每次请求前重新校验（缓解 DNS rebinding）。
"""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_CONFIG = {
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "max_tokens": 1000,
    "monthly_token_budget": 2_000_000,
    "timeout_s": 60,
}


class AIError(Exception):
    """AI 调用失败，消息直接展示给用户。"""


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise AIError("AI 服务地址只支持 http/https")
    host = parsed.hostname
    if not host:
        raise AIError("AI 服务地址缺少主机名")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise AIError(f"AI 服务域名解析失败：{host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise AIError(f"AI 服务地址指向内网/保留地址（{ip}），已拒绝")


def load_ai_config(path: str | Path) -> dict | None:
    """读取并合并配置；缺失/无 Key 时返回 None（AI 功能优雅降级）。"""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        cfg = json.loads(path.read_text(encoding="utf-8")).get("ai") or {}
    except (json.JSONDecodeError, OSError):
        return None
    merged = {**DEFAULT_CONFIG, **cfg}
    if not merged.get("api_key"):
        return None
    try:
        _validate_url(merged["base_url"])
    except AIError as e:
        raise
    return merged


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 禁用重定向


class Provider:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        _validate_url(self.cfg["base_url"])  # 启动即校验，配置错了当场报人话
        self._opener = urllib.request.build_opener(_NoRedirect)

    @property
    def model(self) -> str:
        return str(self.cfg["model"])

    def chat(self, messages: list[dict]) -> tuple[str, int]:
        """一次对话。返回 (回复文本, total_tokens)。失败抛 AIError（人话）。"""
        _validate_url(self.cfg["base_url"])  # 每次请求前复检
        body = {
            "model": self.cfg["model"],
            "messages": messages,
            "max_tokens": int(self.cfg["max_tokens"]),
            "temperature": 0.9,
        }
        req = urllib.request.Request(
            self.cfg["base_url"].rstrip("/") + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.cfg['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener.open(req, timeout=int(self.cfg["timeout_s"])) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:160]
            raise AIError(f"AI 服务返回错误 {e.code}：{detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise AIError(f"连不上 AI 服务：{e}") from e

        try:
            text = payload["choices"][0]["message"]["content"] or ""
            tokens = int(payload.get("usage", {}).get("total_tokens", 0))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise AIError(f"AI 返回格式异常：{str(payload)[:160]}") from e
        return text.strip(), tokens
