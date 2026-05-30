     1|"""
     2|Base platform adapter interface.
     3|
     4|All platform adapters (Telegram, Discord, WhatsApp, Weixin, and more) inherit from this
     5|and implement the required methods.
     6|"""
     7|
     8|import asyncio
     9|import inspect
    10|import ipaddress
    11|import logging
    12|import os
    13|import random
    14|import re
    15|import socket as _socket
    16|import subprocess
    17|import sys
    18|import time
    19|import uuid
    20|from abc import ABC, abstractmethod
    21|from urllib.parse import urlsplit
    22|
    23|from utils import normalize_proxy_url
    24|
    25|logger = logging.getLogger(__name__)
    26|
    27|# Audio file extensions Hermes recognizes for native audio delivery.
    28|# Kept in sync with tools/send_message_tool.py and cron/scheduler.py via
    29|# should_send_media_as_audio() below.
    30|_AUDIO_EXTS = frozenset({'.ogg', '.opus', '.mp3', '.wav', '.m4a', '.flac'})
    31|# Telegram's Bot API sendAudio only accepts MP3 / M4A. Other audio
    32|# formats either need to go through sendVoice (Opus/OGG) or must be
    33|# delivered as a regular document.
    34|_TELEGRAM_AUDIO_ATTACHMENT_EXTS = frozenset({'.mp3', '.m4a'})
    35|_TELEGRAM_VOICE_EXTS = frozenset({'.ogg', '.opus'})
    36|
    37|
    38|def _platform_name(platform) -> str:
    39|    """Normalize a Platform enum / raw string into a lowercase name."""
    40|    value = getattr(platform, "value", platform)
    41|    return str(value or "").lower()
    42|
    43|
    44|def _float_env(name: str, default: float) -> float:
    45|    raw = os.environ.get(name, "").strip()
    46|    if not raw:
    47|        return default
    48|    try:
    49|        return float(raw)
    50|    except (TypeError, ValueError):
    51|        return default
    52|
    53|
    54|def _thread_metadata_for_source(source, reply_to_message_id: str | None = None) -> dict | None:
    55|    """Build platform-aware thread metadata for adapter sends.
    56|
    57|    Most platforms route threaded sends with a generic ``thread_id`` metadata
    58|    value. Telegram private-chat topics created through Hermes' DM-topic helper
    59|    are exposed in updates as ``message_thread_id`` plus a reply anchor. Live
    60|    user-message replies route with ``message_thread_id`` + ``reply_to_message_id``;
    61|    synthetic/resumed sends that have no reply anchor fall back to Telegram's
    62|    ``direct_messages_topic_id`` when the Bot API supports it.
    63|    """
    64|    thread_id = getattr(source, "thread_id", None)
    65|    if thread_id is None:
    66|        return None
    67|    metadata = {"thread_id": thread_id}
    68|    if _platform_name(getattr(source, "platform", None)) == "telegram" and getattr(source, "chat_type", None) == "dm":
    69|        metadata["telegram_dm_topic_reply_fallback"] = True
    70|        tid = str(thread_id)
    71|        if tid and tid not in {"", "1"}:
    72|            metadata["direct_messages_topic_id"] = tid
    73|        anchor = reply_to_message_id or getattr(source, "message_id", None)
    74|        if anchor is not None:
    75|            metadata["telegram_reply_to_message_id"] = str(anchor)
    76|    return metadata
    77|
    78|
    79|def _reply_anchor_for_event(event) -> str | None:
    80|    """Return reply_to id for platforms that need reply semantics.
    81|
    82|    Telegram forum/supergroup topics should be routed by topic metadata, not by
    83|    replying to the triggering message. Hermes-created Telegram private-chat
    84|    topic lanes prefer replying to the triggering user message so the answer
    85|    stays attached to the active lane; synthetic/resumed sends fall back to
    86|    ``direct_messages_topic_id`` metadata when no message id is available.
    87|    """
    88|    source = getattr(event, "source", None)
    89|    platform = _platform_name(getattr(source, "platform", None))
    90|    thread_id = getattr(source, "thread_id", None)
    91|    if platform == "telegram" and thread_id and getattr(source, "chat_type", None) == "dm":
    92|        # Reply to the triggering user message. Replying to Telegram's earlier
    93|        # topic seed/anchor can render the bot response outside the active lane.
    94|        return getattr(event, "message_id", None) or getattr(event, "reply_to_message_id", None)
    95|    if platform == "telegram" and thread_id:
    96|        return None
    97|    if platform == "feishu" and thread_id and getattr(event, "reply_to_message_id", None):
    98|        return getattr(event, "reply_to_message_id", None)
    99|    return getattr(event, "message_id", None)
   100|
   101|
   102|def should_send_media_as_audio(platform, ext: str, is_voice: bool = False) -> bool:
   103|    """Return True when a media file should use the platform's audio sender.
   104|
   105|    Other platforms: every recognized audio extension routes through the
   106|    audio sender.
   107|
   108|    Telegram: the Bot API only accepts MP3/M4A for sendAudio and
   109|    Opus/OGG for sendVoice. Opus/OGG is only routed as audio when the
   110|    caller flagged ``is_voice=True`` (so we don't turn a regular audio
   111|    attachment into a voice bubble just because the file happens to be
   112|    Opus). Everything else falls through to document delivery by
   113|    returning ``False``.
   114|    """
   115|    normalized_ext = (ext or "").lower()
   116|    if normalized_ext not in _AUDIO_EXTS:
   117|        return False
   118|    if _platform_name(platform) == "telegram":
   119|        if normalized_ext in _TELEGRAM_VOICE_EXTS:
   120|            return is_voice
   121|        return normalized_ext in _TELEGRAM_AUDIO_ATTACHMENT_EXTS
   122|    return True
   123|
   124|
   125|def utf16_len(s: str) -> int:
   126|    """Count UTF-16 code units in *s*.
   127|
   128|    Telegram's message-length limit (4 096) is measured in UTF-16 code units,
   129|    **not** Unicode code-points.  Characters outside the Basic Multilingual
   130|    Plane (emoji like 😀, CJK Extension B, musical symbols, …) are encoded as
   131|    surrogate pairs and therefore consume **two** UTF-16 code units each, even
   132|    though Python's ``len()`` counts them as one.
   133|
   134|    Ported from nearai/ironclaw#2304 which discovered the same discrepancy in
   135|    Rust's ``chars().count()``.
   136|    """
   137|    return len(s.encode("utf-16-le")) // 2
   138|
   139|
   140|def _prefix_within_utf16_limit(s: str, limit: int) -> str:
   141|    """Return the longest prefix of *s* whose UTF-16 length ≤ *limit*.
   142|
   143|    Unlike a plain ``s[:limit]``, this respects surrogate-pair boundaries so
   144|    we never slice a multi-code-unit character in half.
   145|    """
   146|    if utf16_len(s) <= limit:
   147|        return s
   148|    # Binary search for the longest safe prefix
   149|    lo, hi = 0, len(s)
   150|    while lo < hi:
   151|        mid = (lo + hi + 1) // 2
   152|        if utf16_len(s[:mid]) <= limit:
   153|            lo = mid
   154|        else:
   155|            hi = mid - 1
   156|    return s[:lo]
   157|
   158|
   159|def _custom_unit_to_cp(s: str, budget: int, len_fn) -> int:
   160|    """Return the largest codepoint offset *n* such that ``len_fn(s[:n]) <= budget``.
   161|
   162|    Used by :meth:`BasePlatformAdapter.truncate_message` when *len_fn* measures
   163|    length in units different from Python codepoints (e.g. UTF-16 code units).
   164|    Falls back to binary search which is O(log n) calls to *len_fn*.
   165|    """
   166|    if len_fn(s) <= budget:
   167|        return len(s)
   168|    lo, hi = 0, len(s)
   169|    while lo < hi:
   170|        mid = (lo + hi + 1) // 2
   171|        if len_fn(s[:mid]) <= budget:
   172|            lo = mid
   173|        else:
   174|            hi = mid - 1
   175|    return lo
   176|
   177|
   178|def is_network_accessible(host: str) -> bool:
   179|    """Return True if *host* would expose the server beyond loopback.
   180|
   181|    Loopback addresses (127.0.0.1, ::1, IPv4-mapped ::ffff:127.0.0.1)
   182|    are local-only.  Unspecified addresses (0.0.0.0, ::) bind all
   183|    interfaces.  Hostnames are resolved; DNS failure fails closed.
   184|    """
   185|    try:
   186|        addr = ipaddress.ip_address(host)
   187|        if addr.is_loopback:
   188|            return False
   189|        # ::ffff:127.0.0.1 — Python reports is_loopback=False for mapped
   190|        # addresses, so check the underlying IPv4 explicitly.
   191|        if getattr(addr, "ipv4_mapped", None) and addr.ipv4_mapped.is_loopback:
   192|            return False
   193|        return True
   194|    except ValueError:
   195|        # when host variable is a hostname, we should try to resolve below
   196|        pass
   197|
   198|    try:
   199|        resolved = _socket.getaddrinfo(
   200|            host, None, _socket.AF_UNSPEC, _socket.SOCK_STREAM,
   201|        )
   202|        # if the hostname resolves into at least one non-loopback address,
   203|        # then we consider it to be network accessible
   204|        for _family, _type, _proto, _canonname, sockaddr in resolved:
   205|            addr = ipaddress.ip_address(sockaddr[0])
   206|            if not addr.is_loopback:
   207|                return True
   208|        return False
   209|    except (_socket.gaierror, OSError):
   210|        return True
   211|
   212|
   213|def _detect_macos_system_proxy() -> str | None:
   214|    """Read the macOS system HTTP(S) proxy via ``scutil --proxy``.
   215|
   216|    Returns an ``http://host:port`` URL string if an HTTP or HTTPS proxy is
   217|    enabled, otherwise *None*.  Falls back silently on non-macOS or on any
   218|    subprocess error.
   219|    """
   220|    if sys.platform != "darwin":
   221|        return None
   222|    try:
   223|        out = subprocess.check_output(
   224|            ["scutil", "--proxy"], timeout=3, text=True, stderr=subprocess.DEVNULL,
   225|        )
   226|    except Exception:
   227|        return None
   228|
   229|    props: dict[str, str] = {}
   230|    for line in out.splitlines():
   231|        line = line.strip()
   232|        if " : " in line:
   233|            key, _, val = line.partition(" : ")
   234|            props[key.strip()] = val.strip()
   235|
   236|    # Prefer HTTPS, fall back to HTTP
   237|    for enable_key, host_key, port_key in (
   238|        ("HTTPSEnable", "HTTPSProxy", "HTTPSPort"),
   239|        ("HTTPEnable", "HTTPProxy", "HTTPPort"),
   240|    ):
   241|        if props.get(enable_key) == "1":
   242|            host = props.get(host_key)
   243|            port = props.get(port_key)
   244|            if host and port:
   245|                return f"http://{host}:{port}"
   246|    return None
   247|
   248|
   249|def _split_host_port(value: str) -> tuple[str, int | None]:
   250|    raw = str(value or "").strip()
   251|    if not raw:
   252|        return "", None
   253|    if "://" in raw:
   254|        parsed = urlsplit(raw)
   255|        return (parsed.hostname or "").lower().rstrip("."), parsed.port
   256|    if raw.startswith("[") and "]" in raw:
   257|        host, _, rest = raw[1:].partition("]")
   258|        port = None
   259|        if rest.startswith(":") and rest[1:].isdigit():
   260|            port = int(rest[1:])
   261|        return host.lower().rstrip("."), port
   262|    if raw.count(":") == 1:
   263|        host, _, maybe_port = raw.rpartition(":")
   264|        if maybe_port.isdigit():
   265|            return host.lower().rstrip("."), int(maybe_port)
   266|    return raw.lower().strip("[]").rstrip("."), None
   267|
   268|
   269|def _no_proxy_entries() -> list[str]:
   270|    entries: list[str] = []
   271|    for key in ("NO_PROXY", "no_proxy"):
   272|        raw = os.environ.get(key, "")
   273|        entries.extend(part.strip() for part in raw.split(",") if part.strip())
   274|    return entries
   275|
   276|
   277|def _no_proxy_entry_matches(entry: str, host: str, port: int | None = None) -> bool:
   278|    token = str(entry or "").strip().lower()
   279|    if not token:
   280|        return False
   281|    if token == "*":
   282|        return True
   283|
   284|    token_host, token_port = _split_host_port(token)
   285|    if token_port is not None and port is not None and token_port != port:
   286|        return False
   287|    if token_port is not None and port is None:
   288|        return False
   289|    if not token_host:
   290|        return False
   291|
   292|    try:
   293|        network = ipaddress.ip_network(token_host, strict=False)
   294|        try:
   295|            return ipaddress.ip_address(host) in network
   296|        except ValueError:
   297|            return False
   298|    except ValueError:
   299|        pass
   300|
   301|    try:
   302|        token_ip = ipaddress.ip_address(token_host)
   303|        try:
   304|            return ipaddress.ip_address(host) == token_ip
   305|        except ValueError:
   306|            return False
   307|    except ValueError:
   308|        pass
   309|
   310|    if token_host.startswith("*."):
   311|        suffix = token_host[1:]
   312|        return host.endswith(suffix)
   313|    if token_host.startswith("."):
   314|        return host == token_host[1:] or host.endswith(token_host)
   315|    return host == token_host or host.endswith(f".{token_host}")
   316|
   317|
   318|def should_bypass_proxy(target_hosts: str | list[str] | tuple[str, ...] | set[str] | None) -> bool:
   319|    """Return True when NO_PROXY/no_proxy matches at least one target host.
   320|
   321|    Supports exact hosts, domain suffixes, wildcard suffixes, IP literals,
   322|    CIDR ranges, optional host:port entries, and ``*``.
   323|    """
   324|    entries = _no_proxy_entries()
   325|    if not entries or not target_hosts:
   326|        return False
   327|    if isinstance(target_hosts, str):
   328|        candidates = [target_hosts]
   329|    else:
   330|        candidates = list(target_hosts)
   331|    for candidate in candidates:
   332|        host, port = _split_host_port(str(candidate))
   333|        if not host:
   334|            continue
   335|        if any(_no_proxy_entry_matches(entry, host, port) for entry in entries):
   336|            return True
   337|    return False
   338|
   339|
   340|def resolve_proxy_url(
   341|    platform_env_var: str | None = None,
   342|    *,
   343|    target_hosts: str | list[str] | tuple[str, ...] | set[str] | None = None,
   344|) -> str | None:
   345|    """Return a proxy URL from env vars, or macOS system proxy.
   346|
   347|    Check order:
   348|      0. *platform_env_var* (e.g. ``DISCORD_PROXY``) — highest priority
   349|      1. HTTPS_PROXY / HTTP_PROXY / ALL_PROXY (and lowercase variants)
   350|      2. macOS system proxy via ``scutil --proxy`` (auto-detect)
   351|
   352|    Returns *None* if no proxy is found, or if NO_PROXY/no_proxy matches one
   353|    of ``target_hosts``.
   354|    """
   355|    if platform_env_var:
   356|        value = (os.environ.get(platform_env_var) or "").strip()
   357|        if value:
   358|            if should_bypass_proxy(target_hosts):
   359|                return None
   360|            return normalize_proxy_url(value)
   361|    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
   362|                "https_proxy", "http_proxy", "all_proxy"):
   363|        value = (os.environ.get(key) or "").strip()
   364|        if value:
   365|            if should_bypass_proxy(target_hosts):
   366|                return None
   367|            return normalize_proxy_url(value)
   368|    detected = normalize_proxy_url(_detect_macos_system_proxy())
   369|    if detected and should_bypass_proxy(target_hosts):
   370|        return None
   371|    return detected
   372|
   373|
   374|def proxy_kwargs_for_bot(proxy_url: str | None) -> dict:
   375|    """Build kwargs for ``commands.Bot()`` / ``discord.Client()`` with proxy.
   376|
   377|    Returns:
   378|      - SOCKS URL  → ``{"connector": ProxyConnector(..., rdns=True)}``
   379|      - HTTP URL   → ``{"proxy": url}``
   380|      - *None*     → ``{}``
   381|
   382|    ``rdns=True`` forces remote DNS resolution through the proxy — required
   383|    by many SOCKS implementations (Shadowrocket, Clash) and essential for
   384|    bypassing DNS pollution behind the GFW.
   385|    """
   386|    if not proxy_url:
   387|        return {}
   388|    if proxy_url.lower().startswith("socks"):
   389|        try:
   390|            from aiohttp_socks import ProxyConnector
   391|
   392|            connector = ProxyConnector.from_url(proxy_url, rdns=True)
   393|            return {"connector": connector}
   394|        except ImportError:
   395|            logger.warning(
   396|                "aiohttp_socks not installed — SOCKS proxy %s ignored. "
   397|                "Run: pip install aiohttp-socks",
   398|                proxy_url,
   399|            )
   400|            return {}
   401|    return {"proxy": proxy_url}
   402|
   403|
   404|def proxy_kwargs_for_aiohttp(proxy_url: str | None) -> tuple[dict, dict]:
   405|    """Build kwargs for standalone ``aiohttp.ClientSession`` with proxy.
   406|
   407|    Returns ``(session_kwargs, request_kwargs)`` where:
   408|      - With aiohttp-socks → ``({"connector": ProxyConnector(...)}, {})``
   409|        for *all* proxy schemes (SOCKS **and** HTTP/HTTPS).
   410|      - HTTP without aiohttp-socks → ``({}, {"proxy": url})``.
   411|      - None → ``({}, {})``.
   412|
   413|    Prefer the connector path: it works transparently with libraries
   414|    (like mautrix) that call ``session.request()`` without forwarding
   415|    per-request ``proxy=`` kwargs.
   416|
   417|    Usage::
   418|
   419|        sess_kw, req_kw = proxy_kwargs_for_aiohttp(proxy_url)
   420|        async with aiohttp.ClientSession(**sess_kw) as session:
   421|            async with session.get(url, **req_kw) as resp:
   422|                ...
   423|    """
   424|    if not proxy_url:
   425|        return {}, {}
   426|    try:
   427|        from aiohttp_socks import ProxyConnector
   428|
   429|        connector = ProxyConnector.from_url(proxy_url, rdns=True)
   430|        return {"connector": connector}, {}
   431|    except ImportError:
   432|        if proxy_url.lower().startswith("socks"):
   433|            logger.warning(
   434|                "aiohttp_socks not installed — SOCKS proxy %s ignored. "
   435|                "Run: pip install aiohttp-socks",
   436|                proxy_url,
   437|            )
   438|            return {}, {}
   439|        return {}, {"proxy": proxy_url}
   440|
   441|
   442|def is_host_excluded_by_no_proxy(hostname: str, no_proxy_value: str | None = None) -> bool:
   443|    """Return True when ``hostname`` matches a ``NO_PROXY`` entry.
   444|
   445|    Supports comma- or whitespace-separated entries with optional leading dots
   446|    and ``*.`` wildcards, which match both the apex domain and subdomains.
   447|    """
   448|    raw = no_proxy_value
   449|    if raw is None:
   450|        raw = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
   451|
   452|    raw = raw.strip()
   453|    if not raw:
   454|        return False
   455|
   456|    lower_hostname = hostname.lower()
   457|    for entry in re.split(r"[\s,]+", raw):
   458|        normalized = entry.strip().lower()
   459|        if not normalized:
   460|            continue
   461|        if normalized == "*":
   462|            return True
   463|
   464|        if normalized.startswith("*."):
   465|            normalized = normalized[2:]
   466|        elif normalized.startswith("."):
   467|            normalized = normalized[1:]
   468|
   469|        if lower_hostname == normalized or lower_hostname.endswith(f".{normalized}"):
   470|            return True
   471|
   472|    return False
   473|
   474|
   475|import dataclasses
   476|from dataclasses import dataclass, field
   477|from datetime import datetime
   478|from pathlib import Path
   479|from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple, Union
   480|from enum import Enum
   481|
   482|from pathlib import Path as _Path
   483|sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
   484|
   485|from gateway.config import Platform, PlatformConfig
   486|from gateway.session import SessionSource, build_session_key
   487|from hermes_constants import get_hermes_dir, get_hermes_home
   488|
   489|
   490|GATEWAY_SECRET_CAPTURE_UNSUPPORTED_MESSAGE = (
   491|    "Secure secret entry is not supported over messaging. "
   492|    "Load this skill in the local CLI to be prompted, or add the key to ~/.hermes/.env manually."
   493|)
   494|
   495|
   496|def safe_url_for_log(url: str, max_len: int = 80) -> str:
   497|    """Return a URL string safe for logs (no query/fragment/userinfo)."""
   498|    if max_len <= 0:
   499|        return ""
   500|
   501|