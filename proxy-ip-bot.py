# In 31 Mordad of 1405, this project was completed and thanks to Dìana for Free Proxy IPs.
# 17:00 PM
import os
import logging
import uuid
import asyncio
import httpx
import io
import re
import ipaddress
import json
import html
from urllib.parse import quote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from telegram.constants import ParseMode, ChatType, ChatMemberStatus
from telegram.error import BadRequest
from termcolor import cprint

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WORKER_URL = "https://Your-Checker.pages.dev" #The source of worker available in repository

DB_FILE = "bot_data.json"
MESSAGE_ENTITY_LIMIT = 45
RISK_SCORE_URL_TEMPLATE = "https://cloudflare-scamalytics.pages.dev/{ip}"

AWAIT_MAIN_INPUT = 0
SELECT_ADD_TYPE, AWAIT_CHAT_ID, AWAIT_ADD_CONFIRMATION, AWAIT_CHAT_NAME = range(1, 5)
SELECT_TARGET_CHAT, SELECT_COMMAND, AWAIT_COMMAND_INPUT, AWAIT_POST_COUNTRY = range(5, 9)
SELECT_CHAT_TO_DELETE, CONFIRM_DELETION = range(9, 11)
AWAIT_DOMAIN_INPUT = 300
AWAIT_POST_DOMAIN_INPUT = 300

COUNTRIES = {
    'ALL': '🌍 All Countries', 'AE': '🇦🇪 UAE', 'AL': '🇦🇱 Albania', 'AM': '🇦🇲 Armenia', 'AR': '🇦🇷 Argentina', 'AT': '🇦🇹 Austria', 'AU': '🇦🇺 Australia', 'AZ': '🇦🇿 Azerbaijan', 'BE': '🇧🇪 Belgium', 'BG': '🇧🇬 Bulgaria', 'BR': '🇧🇷 Brazil', 'CA': '🇨🇦 Canada', 'CH': '🇨🇭 Switzerland', 'CN': '🇨🇳 China', 'CO': '🇨🇴 Colombia', 'CY': '🇨🇾 Cyprus', 'CZ': '🇨🇿 Czechia', 'DE': '🇩🇪 Germany', 'DK': '🇩🇰 Denmark', 'EE': '🇪🇪 Estonia', 'ES': '🇪🇸 Spain', 'FI': '🇫🇮 Finland', 'FR': '🇫🇷 France', 'GB': '🇬🇧 UK', 'GI': '🇬🇮 Gibraltar', 'HK': '🇭🇰 Hong Kong', 'HU': '🇭🇺 Hungary', 'ID': '🇮🇩 Indonesia', 'IE': '🇮🇪 Ireland', 'IL': '🇮🇱 Israel', 'IN': '🇮🇳 India', 'IR': '🇮🇷 Iran', 'IT': '🇮🇹 Italy', 'JP': '🇯🇵 Japan', 'KR': '🇰🇷 South Korea', 'KZ': '🇰🇿 Kazakhstan', 'LT': '🇱🇹 Lithuania', 'LU': '🇱🇺 Luxembourg', 'LV': '🇱🇻 Latvia', 'MD': '🇲🇩 Moldova', 'MX': '🇲🇽 Mexico', 'MY': '🇲🇾 Malaysia', 'NL': '🇳🇱 Netherlands', 'NZ': '🇳🇿 New Zealand', 'PH': '🇵🇭 Philippines', 'PL': '🇵🇱 Poland', 'PR': '🇵🇷 Puerto Rico', 'PT': '🇵🇹 Portugal', 'QA': '🇶🇦 Qatar', 'RO': '🇷🇴 Romania', 'RS': '🇷🇸 Serbia', 'RU': '🇷🇺 Russia', 'SA': '🇸🇦 Saudi Arabia', 'SC': '🇸🇨 Seychelles', 'SE': '🇸🇪 Sweden', 'SG': '🇸🇬 Singapore', 'SK': '🇸🇰 Slovakia', 'TH': '🇹🇭 Thailand', 'TR': '🇹🇷 Turkey', 'TW': '🇹🇼 Taiwan', 'UA': '🇺🇦 Ukraine', 'US': '🇺🇸 USA', 'UZ': '🇺🇿 Uzbekistan', 'VN': '🇻🇳 Vietnam'
}
COUNTRY_URLS = {"ALL": "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/02_proxies.csv"}
COUNTRY_FILE_BASE_URL = "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/"
NUMBER_EMOJIS = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']

def load_db():
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

async def cleanup_deleted_users(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running scheduled job: Cleaning up deleted users...")
    db = load_db()
    
    user_ids_to_check = list(db.keys())
    if not user_ids_to_check:
        logger.info("Cleanup job: Database is empty. Nothing to do.")
        return

    users_deleted_count = 0
    for user_id in user_ids_to_check:
        try:
            await context.bot.get_chat(chat_id=user_id)
            await asyncio.sleep(0.1)
        except BadRequest as e:
            if "chat not found" in e.message.lower():
                logger.info(f"User account {user_id} appears to be deleted. Removing their data.")
                if user_id in db:
                    del db[user_id]
                    users_deleted_count += 1
        except Exception as e:
            logger.error(f"Error checking user {user_id} during cleanup: {e}")

    if users_deleted_count > 0:
        save_db(db)
        logger.info(f"Cleanup finished. Removed data for {users_deleted_count} deleted user(s).")
    else:
        logger.info("Cleanup finished. No deleted users found.")

async def run_periodic_cleanup(application: Application):
    while True:
        await asyncio.sleep(86400)
        try:
            await cleanup_deleted_users(context=application)
        except Exception as e:
            logger.error(f"An error occurred in the periodic cleanup loop: {e}")

RISK_EMOJIS = {"low": "🟢", "medium": "🟡", "high": "🟠", "very_high": "🔴"}

def strip_port(ip: str) -> str:
    """Bracket-aware host extraction. A naive `ip.split(':')[0]` truncates a
    bare IPv6 address (e.g. '2001:db8::1') down to just '2001', since IPv6
    addresses legitimately contain multiple colons themselves."""
    s = (ip or "").strip()
    if s.startswith('[') and ']:' in s:
        return s.split(']:')[0].lstrip('[')
    if s.startswith('[') and s.endswith(']'):
        return s[1:-1]
    if s.count(':') == 1:
        return s.split(':')[0]
    return s.strip('[]')

async def fetch_risk_info(client: httpx.AsyncClient, ip: str) -> dict:
    """Read the actual risk/score JSON from the scamalytics mirror instead of
    just handing the user a link to click. Expected shape:
    {"info": {"success": true, "fraud_score": 23, "risk": "medium"}, "details": {...}}
    """
    clean_ip = strip_port(ip)
    try:
        resp = await client.get(RISK_SCORE_URL_TEMPLATE.format(ip=clean_ip), timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        info = data.get("info", {})
        if info.get("success"):
            return {"risk": info.get("risk", "unknown"), "score": info.get("fraud_score")}
    except Exception as e:
        logger.warning(f"Risk lookup failed for {clean_ip}: {e}")
    return {}

def format_risk_line(risk_data: dict, ip: str) -> str:
    if risk_data and risk_data.get("risk"):
        risk = str(risk_data["risk"])
        score = risk_data.get("score")
        emoji = RISK_EMOJIS.get(risk.lower(), "⚪️")
        score_str = f" (Score: {score})" if score is not None else ""
        return f"{emoji} Risk: {risk.title()}{score_str}"
    clean_ip = strip_port(ip) if ip else ""
    return f"Risk check: {RISK_SCORE_URL_TEMPLATE.format(ip=clean_ip)}"

def _truncate(s: str, n: int) -> str:
    s = s if s else "N/A"
    return s if len(s) <= n else s[:max(0, n - 1)] + "…"

TABLE_COLUMNS = (("#", 4), ("IP", 22), ("Ping", 7), ("Risk", 9), ("Country", 13))

def build_results_table_html(results: list, domain_map: dict = None, range_map: dict = None, start_index: int = 0) -> str:
    """Telegram doesn't render Markdown tables at all, so the closest real
    equivalent is a fixed-width column layout inside a monospace <pre> block
    (HTML parse mode). Returns the raw table text WITHOUT the <pre> wrapper
    so callers can chunk multiple tables before wrapping."""
    header_line = "".join(name.ljust(w) for name, w in TABLE_COLUMNS)
    sep_line = "-" * sum(w for _, w in TABLE_COLUMNS)
    lines = [header_line, sep_line]
    for idx, res in enumerate(results):
        prefix = get_result_source_prefix(res, domain_map, range_map).strip()
        num = prefix if prefix else str(start_index + idx + 1)
        ip_cell = _truncate(res.get('proxyIP', 'N/A'), TABLE_COLUMNS[1][1] - 1)
        ping_value = res.get('ping')
        ping_cell = f"{ping_value}ms" if ping_value is not None else "N/A"
        risk_info = res.get('risk_info') or {}
        risk_cell = _truncate(str(risk_info.get('risk', 'N/A')).title(), TABLE_COLUMNS[3][1] - 1)
        country_cell = _truncate((res.get('info') or {}).get('country', 'N/A'), TABLE_COLUMNS[4][1] - 1)
        row = (num, ip_cell, ping_cell, risk_cell, country_cell)
        lines.append("".join(str(cell).ljust(w) for cell, w in zip(row, (w for _, w in TABLE_COLUMNS))).rstrip())
    return "\n".join(lines)

FAILED_TABLE_COLUMNS = (("#", 4), ("IP", 30))

def build_failed_table_html(failed: list, domain_map: dict = None, range_map: dict = None, start_index: int = 0) -> str:
    """Same fixed-width monospace layout as the successful-IPs table. Only
    lists the failed IPs themselves -- no reason column, since the failure
    reason isn't actionable for the user and the field previously risked
    echoing raw backend/API text."""
    header_line = "".join(name.ljust(w) for name, w in FAILED_TABLE_COLUMNS)
    sep_line = "-" * sum(w for _, w in FAILED_TABLE_COLUMNS)
    lines = [header_line, sep_line]
    for idx, res in enumerate(failed):
        prefix = get_result_source_prefix(res, domain_map, range_map).strip()
        num = prefix if prefix else str(start_index + idx + 1)
        ip_cell = _truncate(res.get('proxyIP', 'N/A'), FAILED_TABLE_COLUMNS[1][1] - 1)
        row = (num, ip_cell)
        lines.append("".join(str(cell).ljust(w) for cell, w in zip(row, (w for _, w in FAILED_TABLE_COLUMNS))).rstrip())
    return "\n".join(lines)

def build_failed_table_markdown(failed: list, domain_map: dict = None, range_map: dict = None) -> str:
    lines = ["| # | IP |", "|---|---|"]
    for idx, res in enumerate(failed):
        prefix = get_result_source_prefix(res, domain_map, range_map).strip() or str(idx + 1)
        ip_cell = str(res.get('proxyIP', 'N/A')).replace('|', '\\|')
        lines.append(f"| {prefix} | `{ip_cell}` |")
    return "\n".join(lines)

def build_results_table_markdown(results: list, domain_map: dict = None, range_map: dict = None) -> str:
    """Native GFM pipe-table markdown. As of Telegram Bot API 10.1 ('Rich
    Messages'), this renders as a REAL table in the client -- no more manual
    monospace <pre> column-padding hacks."""
    lines = ["| # | IP | Ping | Risk | Country |", "|---|---|---|---|---|"]
    for idx, res in enumerate(results):
        prefix = get_result_source_prefix(res, domain_map, range_map).strip() or str(idx + 1)
        ip_cell = str(res.get('proxyIP', 'N/A')).replace('|', '\\|')
        ping_value = res.get('ping')
        ping_cell = f"{ping_value}ms" if ping_value is not None else "N/A"
        risk_info = res.get('risk_info') or {}
        risk_cell = str(risk_info.get('risk', 'N/A')).title()
        country_cell = str((res.get('info') or {}).get('country', 'N/A')).replace('|', '\\|')
        lines.append(f"| {prefix} | `{ip_cell}` | {ping_cell} | {risk_cell} | {country_cell} |")
    return "\n".join(lines)

def build_rich_table_markdown(results: list, title: str, domain_map: dict = None, range_map: dict = None, status_suffix: str = "", failed: list = None) -> str:
    """Wraps the native table in a native <details> block (Rich Markdown allows
    embedding supported HTML tags directly), so it starts collapsed with
    Telegram's own 'Show more' toggle -- the real equivalent of what the old
    blockquote-expandable hack was approximating. Failed IPs (if any) get
    their own separate collapsed <details> block right underneath, so they're
    visible but don't clutter the successful-results view by default.

    The <summary> line itself is kept as short, plain text -- content inside
    an inline HTML tag like <summary> isn't run back through the Markdown
    parser, so any `backtick`/**bold** markers placed there would show up as
    literal characters instead of being rendered. Anything with Markdown
    styling (the per-domain/range list with its `code` ticks) is placed as
    its own line *outside* the <summary>, right above the table, where
    normal Markdown parsing still applies."""
    title_line, *rest = title.split('\n', 1)
    clean_summary = title_line.replace('**', '').strip()
    styled_subtitle = rest[0].strip() if rest else ""
    table_md = build_results_table_markdown(results, domain_map, range_map)
    subtitle_block = f"{styled_subtitle}\n\n" if styled_subtitle else ""
    suffix = f"\n\n{status_suffix}" if status_suffix else ""
    parts = [f"<details><summary>{clean_summary} ({len(results)} successful)</summary>\n\n{subtitle_block}{table_md}{suffix}\n\n</details>"]
    if failed:
        failed_md = build_failed_table_markdown(failed, domain_map, range_map)
        parts.append(f"<details><summary>❌ Failed IPs ({len(failed)})</summary>\n\n{failed_md}\n\n</details>")
    return "\n\n".join(parts)
_rich_capability = {"supported": True}

async def send_rich_or_fallback(bot, chat_id, markdown_text: str, fallback_messages: list[str], fallback_parse_mode=ParseMode.HTML, reply_markup=None) -> bool:
    """Tries native sendRichMessage first; falls back to the legacy HTML
    <pre>+expandable-blockquote messages (already fully chunked/escaped by the
    caller) if rich sending isn't supported or fails for any reason. Returns
    True if the rich path succeeded, False if it fell back."""
    if _rich_capability["supported"]:
        try:
            api_kwargs = {"chat_id": chat_id, "rich_message": {"markdown": markdown_text}}
            if reply_markup:
                api_kwargs["reply_markup"] = reply_markup.to_dict()
            await bot.do_api_request(endpoint="sendRichMessage", api_kwargs=api_kwargs)
            return True
        except BadRequest as e:
            msg = str(e).lower()
            if "method not found" in msg or "unknown method" in msg or "not supported" in msg:
                logger.warning("sendRichMessage isn't supported by this bot/server; disabling rich messages for this run.")
                _rich_capability["supported"] = False
            else:
                logger.warning(f"sendRichMessage failed ({e}); using fallback formatting for this message.")
        except Exception as e:
            logger.warning(f"sendRichMessage failed ({e}); using fallback formatting for this message.")

    for msg_text in fallback_messages:
        try:
            await bot.send_message(chat_id=chat_id, text=msg_text, parse_mode=fallback_parse_mode, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Fallback send also failed: {e}")
    return False

def _strip_md_markers(text: str) -> str:
    """Titles are built once and reused across several send paths (legacy
    Markdown, Rich Markdown, plain HTML). They're written with light Markdown
    styling (**bold**, `code`) for the Markdown paths, but the plain-HTML
    fallback below doesn't parse Markdown at all -- so without stripping
    these markers first, the user would see literal ** and ` characters."""
    return re.sub(r'[`*]', '', text or '')

def wrap_expandable_blockquote(inner_text_html_escaped: str, header_html_escaped: str = "") -> str:
    """Wraps content in Telegram's native collapsible ('expandable') blockquote
    (HTML parse mode: <blockquote expandable>...</blockquote>), so long result
    lists start collapsed behind a 'Show more' toggle instead of dumping a wall
    of text straight into the chat. Both arguments must already be
    HTML-escaped by the caller -- this function does not escape them itself,
    to avoid double-escaping."""
    prefix = f"{header_html_escaped}\n" if header_html_escaped else ""
    return f"{prefix}<blockquote expandable><pre>{inner_text_html_escaped}</pre></blockquote>"

def build_table_messages(results: list, title: str, domain_map: dict = None, range_map: dict = None, status_suffix: str = "", failed: list = None) -> list[str]:
    """Splits results into one or more HTML messages, each an expandable
    monospace table, respecting Telegram's ~4096 char message limit. Failed
    IPs (if any) get their own separate expandable block(s) appended after
    the successful ones."""
    TELEGRAM_LIMIT = 4000
    ROWS_PER_CHUNK = 40
    plain_title = _strip_md_markers(title)
    messages = []
    for i in range(0, len(results), ROWS_PER_CHUNK):
        chunk = results[i:i + ROWS_PER_CHUNK]
        table_text = build_results_table_html(chunk, domain_map, range_map, start_index=i)
        is_first = (i == 0)
        header = html.escape(plain_title) if is_first else html.escape(f"Continuation of {plain_title}")
        body = wrap_expandable_blockquote(html.escape(table_text), header_html_escaped=header)
        if status_suffix and i + ROWS_PER_CHUNK >= len(results):
            body += f"\n{html.escape(status_suffix)}"
        if len(body) > TELEGRAM_LIMIT:
            body = body[:TELEGRAM_LIMIT - 20] + "...</pre></blockquote>"
        messages.append(body)
    if not messages:
        messages = [f"<b>{html.escape(plain_title)}</b>\nNo successful proxies found."]

    if failed:
        for i in range(0, len(failed), ROWS_PER_CHUNK):
            chunk = failed[i:i + ROWS_PER_CHUNK]
            table_text = build_failed_table_html(chunk, domain_map, range_map, start_index=i)
            header = html.escape(f"❌ Failed IPs ({len(failed)})") if i == 0 else html.escape("❌ Failed IPs (continued)")
            body = wrap_expandable_blockquote(html.escape(table_text), header_html_escaped=header)
            if len(body) > TELEGRAM_LIMIT:
                body = body[:TELEGRAM_LIMIT - 20] + "...</pre></blockquote>"
            messages.append(body)

    return messages

async def send_failed_ips_plain_messages(bot, chat_id, failed: list, domain_map: dict = None, range_map: dict = None):
    """Formats 1/4 use legacy Markdown, which has no collapsible-section
    equivalent to Rich Markdown's <details> — failed IPs are sent as their
    own clearly-labelled plain message(s) instead, separate from (and after)
    the successful-results messages. Only lists the IPs themselves; the
    failure reason isn't shown since it's not actionable for the user."""
    if not failed:
        return
    TELEGRAM_LIMIT = 4000
    lines = [f"**❌ Failed IPs ({len(failed)})**", "---"]
    messages = []
    for idx, res in enumerate(failed):
        prefix = get_result_source_prefix(res, domain_map, range_map).strip() or str(idx + 1)
        ip = res.get('proxyIP', 'N/A')
        line = f"{prefix} `{ip}`"
        if len("\n".join(lines)) + len(line) + 2 > TELEGRAM_LIMIT:
            messages.append("\n".join(lines))
            lines = ["**❌ Failed IPs (continued)**", "---", line]
        else:
            lines.append(line)
    if lines:
        messages.append("\n".join(lines))
    for msg in messages:
        try:
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Failed to send failed-IPs message: {e}")

FALLBACK_API_URLS = [
    "https://Your-Server:PORT/api/v1/check?proxyip=",
    "https://Your-Second-API.onrender.com/api/v1/check?proxyip=",
]
# YOU CAN FIND SOURCE IN MY "ProxyIP-Checker-API" REPOSITORY

FALLBACK_API_TIMEOUT = 60.0

async def _check_via_fallback_api(client: httpx.AsyncClient, url: str, proxy_address: str) -> dict:
    """Only used when the Cloudflare Worker domain itself (WORKER_URL) is
    unreachable. Talks directly to a backend checker API, bypassing the
    Worker entirely for this one IP. Results are more bare-bones (no
    Worker-side geo/AS enrichment) but the proxy check itself still happens
    instead of silently failing while the Worker domain is down.

    Each entry in FALLBACK_API_URLS already ends in `?proxyip=`, so the IP is
    appended directly onto the URL string (matching that syntax exactly)
    rather than passed via httpx's `params=`, which merges with -- rather
    than replaces -- an existing query string and would otherwise send the
    IP as a second, duplicate `proxyip` value alongside the empty one baked
    into the URL.

    Always returns a dict (never bare None) so the caller can tell apart
    three genuinely different outcomes: the IP checked out as a working
    proxy (success=True), the backend was reached fine and confirmed it
    ISN'T a working proxy (success=False, reached=True), or the backend
    itself couldn't be reached at all (success=False, reached=False) --
    collapsing the last two into one used to make "the fallback backend is
    down" and "the fallback backend correctly said no" look identical.
    """
    try:
        full_url = f"{url}{quote(proxy_address, safe='')}"
        resp = await client.get(full_url, timeout=FALLBACK_API_TIMEOUT)
        resp.raise_for_status()
        api_data = resp.json()
        if api_data.get('proxyip') is True:
            host = url.split('/')[2] if '//' in url else url
            return {
                'success': True,
                'reached': True,
                'proxyIP': proxy_address,
                'ping': api_data.get('ping'),
                'info': {'country': 'N/A', 'countryCode': 'N/A', 'as': api_data.get('asOrganization', 'N/A')},
                'method': f'Direct Fallback API ({host})',
            }
        return {'success': False, 'reached': True}
    except Exception as e:
        logger.warning(f"Fallback API {url} failed for {proxy_address}: {e!r}")
        return {'success': False, 'reached': False}

async def _check_via_fallback_apis_raced(client: httpx.AsyncClient, proxy_address: str) -> dict:
    """Races every configured fallback backend concurrently and returns
    whichever succeeds first, instead of trying one URL after another. A
    single sleeping/slow free-tier instance (Render cold starts can take
    30-50s) would otherwise sink the whole check even when a second backend
    is perfectly healthy and would have answered in under a second.

    Only returns immediately on a positive hit -- a negative-but-reached
    result keeps the other task(s) running, since one backend confirming
    "not a proxy" doesn't mean a still-pending backend won't confirm the
    opposite. `reached` on the final dict is True as soon as ANY backend
    was actually contacted, even if none of them found a working proxy --
    that's what lets the caller distinguish "fallback ran and said no" from
    "fallback never even got a response"."""
    tasks = [asyncio.create_task(_check_via_fallback_api(client, url, proxy_address)) for url in FALLBACK_API_URLS]
    any_reached = False
    try:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result.get('success'):
                return result
            if result.get('reached'):
                any_reached = True
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
    return {'success': False, 'reached': any_reached}

def _risk_info_from_worker_payload(data: dict) -> dict:
    """The Worker's own /api/check now embeds a risk score directly in its
    response for successful checks. Reuse it when present instead of making
    a second, redundant network call for the exact same data."""
    scam = ((data or {}).get('risk') or {}).get('scamalytics') or {}
    if scam.get('status') == 'ok':
        return {"risk": scam.get('scamalytics_risk', 'unknown'), "score": scam.get('scamalytics_score')}
    return {}

async def validate_proxy_with_worker(ip_obj: dict or str) -> dict:
    proxy_address = ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj
    async with httpx.AsyncClient() as client:
        data = None
        worker_reachable = True
        worker_error = None
        try:
            worker_check_url = f"{WORKER_URL}/api/check/{quote(proxy_address, safe='')}"
            response = await client.get(worker_check_url, timeout=12.0)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            worker_reachable = False
            worker_error = str(e)
            logger.warning(f"Worker unreachable for {proxy_address} ({e!r}); racing direct fallback APIs.")

        if not worker_reachable:
            data = await _check_via_fallback_apis_raced(client, proxy_address)

        def _fail(reason: str) -> dict:
            logger.info(f"Proxy check failed for {proxy_address}: {reason}")
            failure = {"success": False, "proxyIP": proxy_address}
            if isinstance(ip_obj, dict):
                failure.update({k: v for k, v in ip_obj.items() if k != 'ip'})
            return failure

        try:
            if data and data.get("success"):
                if isinstance(ip_obj, dict):
                    data.update(ip_obj)
                risk_info = _risk_info_from_worker_payload(data) if worker_reachable else {}
                if not risk_info:
                    risk_info = await fetch_risk_info(client, data.get('proxyIP', proxy_address))
                data['risk_info'] = risk_info
                data['success'] = True
                return data

            if data and data.get("error"):
                return _fail(data["error"])
            if not worker_reachable:
                if data and data.get("reached"):
                    return _fail(f"Worker unreachable ({worker_error}); fallback API(s) reached and confirmed this is not a valid proxy.")
                return _fail(f"Worker unreachable ({worker_error}) and no fallback API could be reached either.")
            return _fail("Not a valid proxy.")
        except Exception as e:
            logger.error(f"Worker API Error for {proxy_address}: {e}")
            return _fail(str(e))

def parse_ip_range(range_str: str) -> list[str]:
    ips = []
    try:
        if '/' in range_str:
             net = ipaddress.ip_network(range_str, strict=False)
             if net.num_addresses > 65536: return []
             ips = [str(ip) for ip in net.hosts()]
        elif '-' in range_str:
            parts = range_str.split('.')
            if len(parts) == 4 and '-' in parts[3]:
                prefix, start_end = ".".join(parts[:3]), parts[3]
                start, end = map(int, start_end.split('-'))
                if 0 <= start <= end <= 255: ips = [f"{prefix}.{i}" for i in range(start, end + 1)]
    except ValueError as e: logger.warning(f"Invalid range format: {range_str} - {e}")
    return ips

def format_number_with_emojis(n: int) -> str:
    return "".join(NUMBER_EMOJIS[int(digit)] for digit in str(n))

def get_result_source_prefix(res: dict, domain_map: dict = None, range_map: dict = None) -> str:
    prefix = ""
    if domain_map and 'domain_index' in res and res['domain_index'] in domain_map:
        prefix = f"{format_number_with_emojis(res['domain_index'] + 1)} "
    elif range_map and 'range_index' in res and res['range_index'] in range_map:
        prefix = f"{format_number_with_emojis(res['range_index'] + 1)} "
    return prefix

async def _resolve_domain_fallback(client: httpx.AsyncClient, domain: str) -> list[str]:
    """Only used when the Worker's own /api/resolve is unreachable. Queries
    Cloudflare's DNS-over-HTTPS directly for both A and AAAA records — the
    exact same technique the Worker itself uses internally — so a domain
    check still works while the Worker domain is down."""
    ips = []
    headers = {'Accept': 'application/dns-json'}
    try:
        a_resp, aaaa_resp = await asyncio.gather(
            client.get("https://1.1.1.1/dns-query", params={"name": domain, "type": "A"}, headers=headers, timeout=8.0),
            client.get("https://1.1.1.1/dns-query", params={"name": domain, "type": "AAAA"}, headers=headers, timeout=8.0),
            return_exceptions=True
        )
        if isinstance(a_resp, httpx.Response) and a_resp.status_code == 200:
            for ans in a_resp.json().get("Answer", []):
                if ans.get("type") == 1:
                    ips.append(ans["data"])
        if isinstance(aaaa_resp, httpx.Response) and aaaa_resp.status_code == 200:
            for ans in aaaa_resp.json().get("Answer", []):
                if ans.get("type") == 28:
                    ips.append(f"[{ans['data']}]")
    except Exception as e:
        logger.warning(f"DNS fallback failed for {domain}: {e}")
    return ips

async def _resolve_one_domain(client: httpx.AsyncClient, index: int, domain_item: str):
    try:
        params = {'domain': domain_item}
        response = await client.get(f"{WORKER_URL}/api/resolve", params=params, timeout=10.0)
        response.raise_for_status()
        api_result = response.json()
        if api_result.get("success") and api_result.get("ips"):
            return index, domain_item, api_result["ips"]
        raise ValueError(api_result.get("error", "Worker returned no IPs"))
    except Exception as e:
        logger.warning(f"Worker DNS resolve failed for {domain_item} ({e}); using direct DNS fallback.")
        ips = await _resolve_domain_fallback(client, domain_item)
        if not ips:
            logger.error(f"Both Worker and fallback DNS resolution failed for {domain_item}.")
        return index, domain_item, ips

async def _validate_and_resolve_domains(inputs: list) -> (list, str, list, dict):
    invalid_domains = []
    valid_domains = []
    for domain in inputs:
        if domain.lower().startswith('www.') or 'http://' in domain or 'https://' in domain or '/' in domain or not re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$', domain):
            invalid_domains.append(domain)
        else:
            valid_domains.append(domain)

    if invalid_domains:
        invalid_list = "\n".join(f"- `{d}`" for d in invalid_domains)
        error_message = (
            f"Invalid format for the following domain(s).\n"
            f"Do not include `http://`, `https://`, or `www.`.\n\n"
            f"{invalid_list}\n\n"
            f"Example of a correct format:\n"
            f"`di.nscl.ir`"
        )
        return None, error_message, None, None

    ips_to_check, domain_map = [], {}
    async with httpx.AsyncClient() as client:
        resolved = await asyncio.gather(*(
            _resolve_one_domain(client, i, domain_item) for i, domain_item in enumerate(valid_domains)
        ))

    for index, domain_item, ips in resolved:
        if ips:
            domain_map[index] = domain_item
            for ip in ips:
                ips_to_check.append({"ip": ip, "domain_index": index})

    unique_ips_to_check = list({item['ip']: item for item in ips_to_check}.values())
    return valid_domains, None, unique_ips_to_check, domain_map

async def check_ips_and_update_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, ips_to_check: list, title: str, domain_map: dict = None, range_map: dict = None, output_format: str = "4"):
    check_id = str(uuid.uuid4())
    context.user_data[check_id] = {
        'status': 'running', 'ips': ips_to_check, 'checked_ips': set(),
        'successful': [], 'failed': [], 'domain_map': domain_map, 'range_map': range_map,
        'result_message_ids': [message_id], 'output_format': output_format
    }
    
    keyboard = [[
        InlineKeyboardButton("Pause", callback_data=f"pause_{check_id}", style="primary"),
        InlineKeyboardButton("Cancel", callback_data=f"cancel_{check_id}", style="danger")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data[check_id]['markup'] = reply_markup

    initial_text = f"Starting check for {len(ips_to_check)} IPs..."
    try:
        if output_format in ["1", "4"]:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=initial_text, reply_markup=reply_markup)
        else:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔍 Check in progress...")
    except BadRequest:
        try:
            if output_format in ["1", "4"]:
                new_message = await context.bot.send_message(chat_id=chat_id, text=initial_text, reply_markup=reply_markup)
                context.user_data[check_id]['result_message_ids'] = [new_message.message_id]
        except Exception as e:
            logger.error(f"Failed to send new message: {e}")
            return
    
    context.application.create_task(process_ips_in_batches(context, chat_id, check_id, title))

async def process_ips_in_batches(context: ContextTypes.DEFAULT_TYPE, chat_id: int, check_id: str, title: str):
    try:
        check_data = context.user_data.get(check_id)
        if not check_data: return

        domain_map = check_data.get('domain_map')
        range_map = check_data.get('range_map')
        output_format = check_data.get('output_format', "4")
        batch_size = 30
        last_sent_texts = {}
        
        async def check_and_append(ip_obj):
            ip_to_track = ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj
            check_data['checked_ips'].add(ip_to_track)
            result = await validate_proxy_with_worker(ip_obj)
            if result.get('success'):
                check_data['successful'].append(result)
            else:
                check_data['failed'].append(result)

        while len(check_data['checked_ips']) < len(check_data['ips']):
            current_state = context.user_data.get(check_id, {}).get('status', 'stopped')
            if current_state == 'stopped': break
            if current_state == 'paused':
                await asyncio.sleep(1)
                continue

            unchecked_ip_objects = [ip_obj for ip_obj in check_data['ips'] if (ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj) not in check_data['checked_ips']]
            batch = unchecked_ip_objects[:batch_size]
            if not batch:
                logger.warning(f"Check {check_id} stalled. Breaking loop.")
                break
                
            await asyncio.gather(*(check_and_append(ip_obj) for ip_obj in batch))
            
            if output_format in ["1", "4"]:
                messages_to_send = []
                current_parts = []
                
                for overall_idx, res in enumerate(check_data['successful']):
                    if not current_parts:
                        page_index = len(messages_to_send)
                        is_first_page = (page_index == 0)
                        current_title = title if is_first_page else f"**Continuation {title.strip('**')}**"
                        header = f"Checked: {len(check_data['checked_ips'])}/{len(check_data['ips'])} | Successful: {len(check_data['successful'])} | Failed: {len(check_data['failed'])}"
                        current_parts.extend([f"**{current_title}**", header, "---"])

                    number_emoji = ""
                    if domain_map and len(domain_map) > 1 and 'domain_index' in res:
                        number_emoji = format_number_with_emojis(res['domain_index'] + 1)
                    elif range_map and len(range_map) > 1 and 'range_index' in res:
                        number_emoji = format_number_with_emojis(res['range_index'] + 1)
                    else:
                        number_emoji = format_number_with_emojis(overall_idx + 1)

                    geo_info = res.get('info', {})
                    as_name = geo_info.get('as', 'N/A')
                    if len(as_name) > 70: as_name = as_name[:67] + '...'

                    ping_value = res.get('ping')
                    ping_str = f" - Ping : {ping_value} ms" if ping_value is not None else ""
                    details = f"({geo_info.get('country', 'N/A')} - {as_name}{ping_str})"
                    
                    line1 = f"{number_emoji} {res.get('proxyIP')} {details}"
                    line2 = format_risk_line(res.get('risk_info'), res.get('proxyIP'))
                    full_content_for_block = f"{line1}\n{line2}"
                    new_line = f"```{full_content_for_block}```"

                    if len("\n".join(current_parts)) + len(new_line) + 2 > 4000:
                        messages_to_send.append("\n".join(current_parts))
                        header = f"Checked: {len(check_data['checked_ips'])}/{len(check_data['ips'])} | Successful: {len(check_data['successful'])} | Failed: {len(check_data['failed'])}"
                        current_parts = [f"**Continuation {title.strip('**')}**", header, "---", new_line]
                    else:
                        current_parts.append(new_line)

                if current_parts:
                    messages_to_send.append("\n".join(current_parts))

                for i, text_content in enumerate(messages_to_send):
                    try:
                        last_sent_texts[i] = text_content
                        is_first_message = (i == 0)
                        current_markup = check_data.get('markup') if is_first_message else None
                        if i >= len(check_data['result_message_ids']):
                            new_msg = await context.bot.send_message(chat_id=chat_id, text=text_content, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup, disable_web_page_preview=True)
                            check_data['result_message_ids'].append(new_msg.message_id)
                        else:
                            message_id = check_data['result_message_ids'][i]
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_content, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup, disable_web_page_preview=True)
                    except BadRequest as e:
                        if "Message is not modified" not in str(e): logger.warning(f"Update failed for message page {i}: {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error during update for message page {i}: {e}")

            await asyncio.sleep(1.5)

        status = "Cancelled" if context.user_data.get(check_id, {}).get('status') == 'stopped' else "Completed"
        
        if output_format in ["1", "4"]:
            for i, message_id in enumerate(check_data['result_message_ids']):
                try:
                    final_text = last_sent_texts.get(i)
                    if i == 0 and not check_data['successful']:
                        final_text = f"**{title}**\nNo successful proxies found."
                    if not final_text: continue
                    if f"Check {status}" not in final_text:
                        final_text += f"\n\n**Check {status}.**"
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode=ParseMode.MARKDOWN, reply_markup=None, disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Error during finalization of message {message_id}: {e}")
            if check_data['failed']:
                await asyncio.sleep(0.3)
                await send_failed_ips_plain_messages(context.bot, chat_id, check_data['failed'], domain_map, range_map)

        if output_format == "5":
            status_suffix = f"Check {status}. ({len(check_data['checked_ips'])}/{len(check_data['ips'])} checked, {len(check_data['successful'])} successful, {len(check_data['failed'])} failed)"
            rich_markdown = build_rich_table_markdown(check_data['successful'], title, domain_map, range_map, status_suffix=status_suffix, failed=check_data['failed'])
            fallback_messages = build_table_messages(check_data['successful'], title, domain_map, range_map, status_suffix=status_suffix, failed=check_data['failed'])
            await send_rich_or_fallback(context.bot, chat_id, rich_markdown, fallback_messages)

        if check_data['successful']:
            final_sorted_ips = sorted([res['proxyIP'] for res in check_data['successful']], key=lambda ip: ipaddress.ip_address(strip_port(ip)))
            copy_text = "\n".join(final_sorted_ips)
            
            if output_format in ["2", "4", "5"]:
                await context.bot.send_message(chat_id=chat_id, text=f"To copy all IPs, tap the code block below:\n```\n{copy_text}\n```", parse_mode=ParseMode.MARKDOWN_V2)

            if output_format in ["3", "4"]:
                file_name = f"successful_proxies_{uuid.uuid4().hex[:6]}"
                txt_file = io.BytesIO(copy_text.encode('utf-8'))
                await context.bot.send_document(chat_id=chat_id, document=txt_file, filename=f"{file_name}.txt")
                csv_file = io.BytesIO(copy_text.encode('utf-8'))
                await context.bot.send_document(chat_id=chat_id, document=csv_file, filename=f"{file_name}.csv")
              
        if output_format in ["2", "3"]:
            for m_id in check_data.get('result_message_ids', []):
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=m_id)
                except Exception:
                    pass

    finally:
        if check_id in context.user_data: del context.user_data[check_id]

async def run_check_and_post(context: ContextTypes.DEFAULT_TYPE, target_chat_id, ips_to_check: list, title: str, confirmation_message, domain_map: dict = None, range_map: dict = None, output_format: str = "4"):
    try:
        successful_results_with_info = []
        failed_results = []
        batch_size = 30
        for i in range(0, len(ips_to_check), batch_size):
            batch = ips_to_check[i:i + batch_size]
            results = await asyncio.gather(*(validate_proxy_with_worker(ip_obj) for ip_obj in batch))
            for res in results:
                (successful_results_with_info if res.get('success') else failed_results).append(res)
            await asyncio.sleep(1)

        if not successful_results_with_info:
            no_success_text = f"**{title}**\nNo successful proxies found. ({len(failed_results)} failed)"
            await context.bot.send_message(chat_id=target_chat_id, text=no_success_text, parse_mode=ParseMode.MARKDOWN)
            if failed_results and output_format in ["1", "4"]:
                await send_failed_ips_plain_messages(context.bot, target_chat_id, failed_results, domain_map, range_map)
            return

        if output_format in ["1", "4"]:
            TELEGRAM_MESSAGE_LIMIT = 4000
            message_parts = []
            message_count = 0
            for res_index, res in enumerate(successful_results_with_info):
                if not message_parts:
                    message_count += 1
                    is_first_message = (message_count == 1)
                    current_title = title if is_first_message else f"**Continuation {title.strip('**')}**"
                    message_parts.extend([f"**{current_title}**", "---"])
                number_emoji = ""
                if domain_map and len(domain_map) > 1 and 'domain_index' in res:
                    number_emoji = format_number_with_emojis(res['domain_index'] + 1)
                elif range_map and len(range_map) > 1 and 'range_index' in res:
                    number_emoji = format_number_with_emojis(res['range_index'] + 1)
                else:
                    number_emoji = format_number_with_emojis(res_index + 1)
                geo_info = res.get('info', {})
                as_name = geo_info.get('as', 'N/A')
                if len(as_name) > 70: as_name = as_name[:67] + '...'
                ping_value = res.get('ping')
                ping_str = f" - Ping : {ping_value} ms" if ping_value is not None else ""
                details = f"({geo_info.get('country', 'N/A')} - {as_name}{ping_str})"
                line1 = f"{number_emoji} {res.get('proxyIP')} {details}"
                line2 = format_risk_line(res.get('risk_info'), res.get('proxyIP'))
                full_content_for_block = f"{line1}\n{line2}"
                new_line = f"```{full_content_for_block}```"
                if len("\n".join(message_parts)) + len(new_line) + 2 > TELEGRAM_MESSAGE_LIMIT:
                    await context.bot.send_message(chat_id=target_chat_id, text="\n".join(message_parts), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                    await asyncio.sleep(0.5)
                    message_count += 1
                    new_title = f"**Continuation {title.strip('**')}**"
                    message_parts = [new_title, "---", new_line]
                else:
                    message_parts.append(new_line)
            if message_parts:
                message_parts.append(f"\n**Check Completed.** ({len(successful_results_with_info)} successful, {len(failed_results)} failed)")
                final_message_text = "\n".join(message_parts)
                await context.bot.send_message(chat_id=target_chat_id, text=final_message_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                await asyncio.sleep(0.5)

            if failed_results:
                await asyncio.sleep(0.3)
                await send_failed_ips_plain_messages(context.bot, target_chat_id, failed_results, domain_map, range_map)

        if output_format == "5":
            status_suffix = f"Check Completed. ({len(successful_results_with_info)} successful, {len(failed_results)} failed)"
            rich_markdown = build_rich_table_markdown(successful_results_with_info, title, domain_map, range_map, status_suffix=status_suffix, failed=failed_results)
            fallback_messages = build_table_messages(successful_results_with_info, title, domain_map, range_map, status_suffix=status_suffix, failed=failed_results)
            await send_rich_or_fallback(context.bot, target_chat_id, rich_markdown, fallback_messages)

        final_sorted_ips = sorted([res['proxyIP'] for res in successful_results_with_info], key=lambda ip: ipaddress.ip_address(strip_port(ip)))
        copy_text = "\n".join(final_sorted_ips)
        
        if output_format in ["2", "4", "5"]:
            await context.bot.send_message(chat_id=target_chat_id, text=f"To copy all IPs, tap the code block below:\n```\n{copy_text}\n```", parse_mode=ParseMode.MARKDOWN_V2)
        
        if output_format in ["3", "4"]:
            file_name = f"successful_proxies_{uuid.uuid4().hex[:6]}"
            txt_file = io.BytesIO(copy_text.encode('utf-8'))
            await context.bot.send_document(chat_id=target_chat_id, document=txt_file, filename=f"{file_name}.txt")
            csv_file = io.BytesIO(copy_text.encode('utf-8'))
            await context.bot.send_document(chat_id=target_chat_id, document=csv_file, filename=f"{file_name}.csv")

    except Exception as e:
        logger.error(f"Error in run_check_and_post: {e}")
        await context.bot.send_message(chat_id=confirmation_message.chat_id, text=f"An unexpected error occurred while posting: {e}")
    finally:
        try: await context.bot.delete_message(chat_id=confirmation_message.chat_id, message_id=confirmation_message.message_id)
        except Exception: pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("👋 Welcome! Use the menu commands to start.")

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.edit_message_text("Operation cancelled.")
    elif update.message:
        await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def start_main_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    command_text = update.message.text.split()[0]
    command = command_text.replace('/', '').split('@')[0]
    if '@' in command_text and update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text(f"Please use the command without mentioning the bot's name, like `/{command}`.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    if update.message.chat.type != ChatType.PRIVATE:
        prompt_message = await update.message.reply_text(f"To use `/{command}`, please **reply** to this message with your input.", parse_mode=ParseMode.MARKDOWN)
        context.chat_data[str(prompt_message.message_id)] = {"command": command, "user_id": update.message.from_user.id}
        return AWAIT_MAIN_INPUT
    if context.args:
        sent_message = await update.message.reply_text(f"Processing your request...")
        await process_command_logic(update, context, command, context.args, sent_message)
        return ConversationHandler.END
    else:
        prompts = {'proxyip': "Please send your IP(s).", 'iprange': "Please send your IP range(s).", 'file': "Please send the file URL."}
        await update.message.reply_text(prompts.get(command, "Please send your input."))
        context.user_data['command_in_progress'] = command
        return AWAIT_MAIN_INPUT

async def handle_main_conversation_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    command = None
    if update.message.chat.type != ChatType.PRIVATE:
        if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
            prompt_message_id = str(update.message.reply_to_message.message_id)
            if prompt_message_id in context.chat_data:
                stored_data = context.chat_data.pop(prompt_message_id)
                if stored_data and stored_data["user_id"] == update.message.from_user.id:
                    command = stored_data['command']
    else:
        command = context.user_data.pop('command_in_progress', None)
    if not command: return ConversationHandler.END
    sent_message = await update.message.reply_text("Input received. Preparing...")
    inputs = update.message.text.split()
    await process_command_logic(update, context, command, inputs, sent_message)
    return ConversationHandler.END

def get_format_keyboard(user_id, data_key):
    keyboard = [
        [InlineKeyboardButton("Detailed Info", callback_data=f"fmt_1_{user_id}_{data_key}", style="primary")],
        [InlineKeyboardButton("Rich Table (Collapsible)", callback_data=f"fmt_5_{user_id}_{data_key}", style="primary")],
        [InlineKeyboardButton("Copyable IPs", callback_data=f"fmt_2_{user_id}_{data_key}", style="primary")],
        [InlineKeyboardButton("Files (TXT/CSV)", callback_data=f"fmt_3_{user_id}_{data_key}", style="primary")],
        [InlineKeyboardButton("All Formats", callback_data=f"fmt_4_{user_id}_{data_key}", style="success")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def process_command_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str, inputs: list, message):
    user_id = update.effective_user.id
    data_key = str(uuid.uuid4())
    context.user_data[data_key] = {"command": command, "inputs": inputs, "message_id": message.message_id}
    await message.edit_text("Please select the output format you prefer:", reply_markup=get_format_keyboard(user_id, data_key))

async def format_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, out_fmt, creator_id, data_key = query.data.split('_')
    
    if str(query.from_user.id) != creator_id:
        await query.answer("This menu is only for the user who initiated the command.", show_alert=True)
        return

    await query.answer()
    data = context.user_data.get(data_key)
    if not data:
        await query.edit_message_text("Session expired. Please start over.")
        return

    command, inputs, msg_id = data['command'], data['inputs'], data['message_id']
    chat_id = query.message.chat_id
    
    if 'target_chat_id' in data:
        target_chat_id = data['target_chat_id']
        confirmation_msg = query.message
        context.application.create_task(run_post_command_logic(context, target_chat_id, command, inputs, confirmation_msg, output_format=out_fmt, title_prefix=data.get('title_prefix', "")))
        return

    ips_with_context = []
    if command == "proxyip":
        ips_with_context = [{"ip": ip} for ip in inputs]
        await check_ips_and_update_message(context, chat_id, msg_id, ips_with_context, "Proxy IP Results", output_format=out_fmt)
    elif command == "iprange":
        range_map = {}
        for i, range_str in enumerate(inputs):
            range_map[i] = range_str
            for ip in parse_ip_range(range_str):
                ips_with_context.append({"ip": ip, "range_index": i})
        title_header = "**Results for IP Range(s):**"
        title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in range_map.items()]
        title = f"{title_header}\n" + "\n".join(title_parts)
        if not ips_with_context: await query.edit_message_text("Invalid range format or no IPs found.")
        else: await check_ips_and_update_message(context, chat_id, msg_id, ips_with_context, title, range_map=range_map, output_format=out_fmt)
    elif command == "file":
        file_url = inputs[0]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', text)))
            ips_with_context = [{"ip": ip} for ip in ips_found]
            if not ips_with_context: await query.edit_message_text("No valid IPs found in the file.")
            else: await check_ips_and_update_message(context, chat_id, msg_id, ips_with_context, "File Check Results", output_format=out_fmt)
        except Exception as e: await query.edit_message_text(f"Error processing file: {e}")
    elif command == "domain":
        valid_domains, error_message, ips_to_check, domain_map = await _validate_and_resolve_domains(inputs)
        if len(valid_domains) > 1:
            title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in domain_map.items()]
            title = "**Results for Domains:**\n" + "\n".join(title_parts)
        else: title = f"**Results for:** `{valid_domains[0]}`"
        if not ips_to_check: await query.edit_message_text("Could not resolve any IPs.")
        else: await check_ips_and_update_message(context, chat_id, msg_id, ips_to_check, title, domain_map=domain_map, output_format=out_fmt)
    elif command == "freeproxyip":
        country_code = inputs[0]
        country_name = COUNTRIES.get(country_code, "Selected Country")
        url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                response.raise_for_status()
                ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', response.text)))
            ips_with_context = [{"ip": ip} for ip in ips_found]
            if not ips_with_context: await query.edit_message_text(f"No IPs found for {country_name}.")
            else: await check_ips_and_update_message(context, chat_id, msg_id, ips_with_context, f"**{country_name} Check Results**", output_format=out_fmt)
        except Exception as e: await query.edit_message_text(f"Error: {e}")

async def domain_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text(f"Please use `/domain` without mentioning the bot's name.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    if context.args: return await validate_and_process_domains(update, context, context.args)
    await update.message.reply_text("Please send the domain(s) you want to check.\nTo cancel at any time, send /cancel.")
    return AWAIT_DOMAIN_INPUT

async def handle_domain_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    inputs = update.message.text.split()
    return await validate_and_process_domains(update, context, inputs)

async def validate_and_process_domains(update: Update, context: ContextTypes.DEFAULT_TYPE, inputs: list) -> int:
    valid_domains, error_message, ips_to_check, domain_map = await _validate_and_resolve_domains(inputs)
    if error_message:
        await update.message.reply_text(f"{error_message}\n\nPlease send the corrected domain(s), or /cancel to quit.", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_DOMAIN_INPUT
    sent_message = await update.message.reply_text(f"Preparing to check {len(valid_domains)} domain(s)...")
    user_id = update.effective_user.id
    data_key = str(uuid.uuid4())
    context.user_data[data_key] = {"command": "domain", "inputs": inputs, "message_id": sent_message.message_id}
    await sent_message.edit_text("Please select the output format you prefer:", reply_markup=get_format_keyboard(user_id, data_key))
    return ConversationHandler.END

async def freeproxyip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text(f"Please use `/freeproxyip` without mentioning the bot's name.", parse_mode=ParseMode.MARKDOWN)
        return
    keyboard = []
    row = []
    sorted_countries = sorted([(code, name) for code, name in COUNTRIES.items() if code != 'ALL'], key=lambda item: item[1])
    sorted_countries.insert(0, ('ALL', COUNTRIES['ALL']))
    for code, name in sorted_countries:
        row.append(InlineKeyboardButton(name, callback_data=f"country_{code}"))
        if len(row) == 3: keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="freeproxy_cancel")])
    await update.message.reply_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))

async def addchat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("To use this command, please send it to me in a private chat.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton("Group", callback_data="addtype_group"), InlineKeyboardButton("Channel", callback_data="addtype_channel")]]
    await update.message.reply_text("Which do you want to add?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_ADD_TYPE

async def addchat_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chat_type = query.data.split('_')[-1]
    context.user_data['add_chat_type'] = chat_type
    if chat_type == 'channel': prompt = "Please send the channel username (e.g., @mychannel)."
    else: prompt = "Please send the group's numerical ID."
    await query.edit_message_text(prompt)
    return AWAIT_CHAT_ID

async def addchat_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id_str = update.message.text.strip()
    user_id = update.effective_user.id
    waiting_message = await update.message.reply_text("Verifying permissions, please wait...")
    try:
        bot_member = await context.bot.get_chat_member(chat_id=chat_id_str, user_id=context.bot.id)
        chat_type = context.user_data.get('add_chat_type')
        if chat_type == 'channel':
            if not (bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_post_messages):
                await waiting_message.edit_text("Error: Bot lacks post permissions.")
                return ConversationHandler.END
        elif chat_type == 'group':
            if bot_member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await waiting_message.edit_text("Error: Bot not in group.")
                return ConversationHandler.END
        user_member = await context.bot.get_chat_member(chat_id=chat_id_str, user_id=user_id)
        if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await waiting_message.edit_text("Error: You must be admin.")
            return ConversationHandler.END
        target_chat = await context.bot.get_chat(chat_id=chat_id_str)
        context.user_data['new_chat_id'] = target_chat.id
        context.user_data['new_chat_title'] = target_chat.title
        await waiting_message.edit_text(f"✅ Verified '{target_chat.title}'! Send a custom name now.")
        return AWAIT_CHAT_NAME
    except Exception as e:
        await waiting_message.edit_text(f"Verification error: {e}")
        return ConversationHandler.END

async def addchat_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_str = str(update.message.from_user.id)
    name, chat_id = update.message.text, context.user_data.pop('new_chat_id', None)
    if not chat_id: return ConversationHandler.END
    db = load_db()
    user_chats = db.get(user_id_str, [])
    if not any(c['chat_id'] == chat_id for c in user_chats):
        user_chats.append({"chat_id": chat_id, "name": name})
        db[user_id_str] = user_chats
        save_db(db)
        await update.message.reply_text(f"✅ Destination '{name}' registered!")
    else: await update.message.reply_text("Already registered.")
    context.user_data.clear()
    return ConversationHandler.END

async def deletechat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Private chat only.")
        return ConversationHandler.END
    user_chats = load_db().get(str(update.message.from_user.id), [])
    if not user_chats:
        await update.message.reply_text("No saved chats.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(chat['name'], callback_data=f"del_chat_{chat['chat_id']}")] for chat in user_chats]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="del_cancel")])
    await update.message.reply_text("Select destination to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_CHAT_TO_DELETE

async def deletechat_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "del_cancel":
        await query.edit_message_text("Cancelled.")
        return ConversationHandler.END
    context.user_data['chat_to_delete'] = query.data.split('_')[-1]
    keyboard = [[InlineKeyboardButton("✅ Yes", callback_data="del_confirm_yes", style="danger"), InlineKeyboardButton("❌ No", callback_data="del_confirm_no", style="primary")]]
    await query.edit_message_text("Are you sure?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_DELETION

async def deletechat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id_str, db = str(query.from_user.id), load_db()
    if query.data == "del_confirm_no": return await deletechat_start(update, context)
    chat_id_to_delete = context.user_data.pop('chat_to_delete', None)
    user_chats = db.get(user_id_str, [])
    db[user_id_str] = [chat for chat in user_chats if str(chat['chat_id']) != str(chat_id_to_delete)]
    save_db(db)
    await query.edit_message_text("✅ Deleted.")
    return ConversationHandler.END

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Private chat only.")
        return ConversationHandler.END
    user_chats = load_db().get(str(update.message.from_user.id), [])
    if not user_chats:
        await update.message.reply_text("Use /addchat first.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(chat['name'], callback_data=f"post_chat_{chat['chat_id']}")] for chat in user_chats]
    await update.message.reply_text("Select destination:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_TARGET_CHAT

async def post_select_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['target_chat_id'] = query.data.split('_')[-1]
    keyboard = [
        [InlineKeyboardButton("Proxy IP Check", callback_data="post_cmd_proxyip")],
        [InlineKeyboardButton("IP Range Check", callback_data="post_cmd_iprange")],
        [InlineKeyboardButton("Domain Check", callback_data="post_cmd_domain")],
        [InlineKeyboardButton("File URL Check", callback_data="post_cmd_file")],
        [InlineKeyboardButton("✨ Free Proxies by Country", callback_data="post_cmd_freeproxyip")],
    ]
    await query.edit_message_text("Select check type:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_COMMAND

async def post_select_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    command = query.data.split('_')[-1]
    context.user_data['post_command'] = command
    if command == 'freeproxyip':
        keyboard = []
        row = []
        sorted_countries = sorted([(code, name) for code, name in COUNTRIES.items() if code != 'ALL'], key=lambda item: item[1])
        sorted_countries.insert(0, ('ALL', COUNTRIES['ALL']))
        for code, name in sorted_countries:
            row.append(InlineKeyboardButton(name, callback_data=f"post_country_{code}"))
            if len(row) == 3: keyboard.append(row); row = []
        if row: keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="post_cmd_back")])
        await query.edit_message_text("Select country:", reply_markup=InlineKeyboardMarkup(keyboard))
        return AWAIT_POST_COUNTRY
    else:
        await query.edit_message_text(f"Send input for `{command}`.", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_COMMAND_INPUT

async def post_handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_chat_id_str, command = context.user_data.get('target_chat_id'), context.user_data.get('post_command')
    inputs = update.message.text.split()
    sent_msg = await update.message.reply_text("Input received. Preparing...")
    user_id = update.effective_user.id
    data_key = str(uuid.uuid4())
    context.user_data[data_key] = {"command": command, "inputs": inputs, "target_chat_id": target_chat_id_str, "message_id": sent_msg.message_id}
    await sent_msg.edit_text("Select output format for destination:", reply_markup=get_format_keyboard(user_id, data_key))
    return ConversationHandler.END

async def post_handle_domain_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    inputs = update.message.text.split()
    valid_domains, error_message, _, _ = await _validate_and_resolve_domains(inputs)
    if error_message:
        await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN)
        return AWAIT_POST_DOMAIN_INPUT
    target_chat_id_str, command = context.user_data.get('target_chat_id'), context.user_data.get('post_command')
    sent_msg = await update.message.reply_text("Domains received. Preparing...")
    user_id = update.effective_user.id
    data_key = str(uuid.uuid4())
    context.user_data[data_key] = {"command": command, "inputs": valid_domains, "target_chat_id": target_chat_id_str, "message_id": sent_msg.message_id}
    await sent_msg.edit_text("Select output format for destination:", reply_markup=get_format_keyboard(user_id, data_key))
    return ConversationHandler.END

async def post_handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "post_cmd_back": return await post_select_chat(update, context)
    target_chat_id_str, country_code = context.user_data.get('target_chat_id'), query.data.split('_')[-1]
    country_name = COUNTRIES.get(country_code, "Country")
    user_id = query.from_user.id
    data_key = str(uuid.uuid4())
    context.user_data[data_key] = {"command": "freeproxyip", "inputs": [country_code], "target_chat_id": target_chat_id_str, "title_prefix": f"**{country_name} Check Results**", "message_id": query.message.message_id}
    await query.edit_message_text(f"Select output format for {country_name}:", reply_markup=get_format_keyboard(user_id, data_key))
    return ConversationHandler.END

async def run_post_command_logic(context: ContextTypes.DEFAULT_TYPE, target_chat_id_str: str, command: str, inputs: list, confirmation_message, output_format: str = "4", title_prefix: str = ""):
    ips_to_check, domain_map, range_map, title = [], {}, {}, title_prefix
    try: target_chat_id = int(target_chat_id_str) if target_chat_id_str.startswith('-') else target_chat_id_str
    except: target_chat_id = target_chat_id_str
    try:
        if command == "proxyip":
            ips_to_check, title = [{"ip": ip} for ip in inputs], title or "Proxy IP Check Results:"
        elif command == "iprange":
            for i, r in enumerate(inputs):
                range_map[i] = r
                for ip in parse_ip_range(r): ips_to_check.append({"ip": ip, "range_index": i})
            title = f"**Results for IP Range(s):**\n" + "\n".join([f"{format_number_with_emojis(i+1)} `{n}`" for i, n in range_map.items()])
        elif command == "domain":
            _, _, ips_to_check, domain_map = await _validate_and_resolve_domains(inputs)
            title = f"**Results for:**\n" + "\n".join([f"{format_number_with_emojis(i+1)} `{n}`" for i, n in domain_map.items()][:20])
        elif command == "file":
            async with httpx.AsyncClient() as client:
                response = await client.get(inputs[0], timeout=15)
                ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', response.text)))
                ips_to_check = [{"ip": ip} for ip in ips_found]
            title = title or "File Check Results:"
        elif command == "freeproxyip":
            country_code = inputs[0]
            url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', response.text)))
                ips_to_check = [{"ip": ip} for ip in ips_found]
            title = title_prefix or f"{COUNTRIES.get(country_code)} Check Results:"
        if not ips_to_check:
            await context.bot.send_message(chat_id=target_chat_id, text="⚠️ *No IPs found.*", parse_mode=ParseMode.MARKDOWN)
            return
        await confirmation_message.edit_text("🚀 Check started in background. Results will be posted to destination.")
        await run_check_and_post(context, target_chat_id, ips_to_check, title, confirmation_message, domain_map, range_map, output_format=output_format)
    except Exception as e:
        await context.bot.send_message(chat_id=confirmation_message.chat_id, text=f"❌ *Error:* `{e}`", parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split('_', 1)
    callback_type, data = parts[0], (parts[1] if len(parts) > 1 else None)
    
    if callback_type == "fmt": return await format_selection_callback(update, context)
    
    if callback_type == "freeproxy" and data == "cancel":
        await query.answer(); await query.edit_message_text("Cancelled."); return

    if callback_type == "country":
        await query.answer()
        country_code = data
        user_id = query.from_user.id
        data_key = str(uuid.uuid4())
        context.user_data[data_key] = {"command": "freeproxyip", "inputs": [country_code], "message_id": query.message.message_id}
        await query.edit_message_text(f"Select output format for {COUNTRIES.get(country_code)}:", reply_markup=get_format_keyboard(user_id, data_key))
        return

    check_id = data
    if not check_id or check_id not in context.user_data:
        await query.answer("Expired.", show_alert=True); return

    if context.user_data[check_id].get('is_modifying_state', False): return
    context.user_data[check_id]['is_modifying_state'] = True
    try:
        current_status = context.user_data[check_id].get('status')
        if callback_type == 'pause':
            context.user_data[check_id]['status'] = 'paused'
            keyboard = [[InlineKeyboardButton("Resume", callback_data=f"resume_{check_id}", style="success"), InlineKeyboardButton("Cancel", callback_data=f"cancel_{check_id}", style="danger")]]
            context.user_data[check_id]['markup'] = InlineKeyboardMarkup(keyboard)
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        elif callback_type == 'resume':
            context.user_data[check_id]['status'] = 'running'
            keyboard = [[InlineKeyboardButton("Pause", callback_data=f"pause_{check_id}", style="primary"), InlineKeyboardButton("Cancel", callback_data=f"cancel_{check_id}", style="danger")]]
            context.user_data[check_id]['markup'] = InlineKeyboardMarkup(keyboard)
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        elif callback_type == 'cancel':
            context.user_data[check_id]['status'] = 'stopped'
            await query.edit_message_reply_markup(reply_markup=None)
    finally:
        if check_id in context.user_data: context.user_data[check_id]['is_modifying_state'] = False

async def post_init(application: Application):
    commands = [
        BotCommand("start", "🤖 Start Using Bot"),
        BotCommand("proxyip", "🔍 Check Proxy IPs"),
        BotCommand("iprange", "🔍 Check Proxy IP Ranges"),
        BotCommand("domain", "🔍 Resolving Domains"),
        BotCommand("file", "🔍 Check Proxy IPs From File"),
        BotCommand("freeproxyip", "✨ Get Free Proxies"),
        BotCommand("addchat", "➕ Register Chat"),
        BotCommand("deletechat", "🗑️ Delete Chat"),
        BotCommand("post", "🚀 Post Results"),
        BotCommand("cancel", "❌ Cancel"),
    ]
    await application.bot.set_my_commands(commands)
    application.create_task(run_periodic_cleanup(application))
    
def main() -> None:
    cprint("made with ❤️‍🔥 by @mehdiasmart", "light_cyan")
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    main_conv = ConversationHandler(
        entry_points=[CommandHandler(cmd, start_main_conversation) for cmd in ["proxyip", "iprange", "file"]],
        states={AWAIT_MAIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_conversation_input)]},
        fallbacks=[CommandHandler("domain", domain_start), CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True
    )
    domain_conv = ConversationHandler(
        entry_points=[CommandHandler("domain", domain_start)],
        states={AWAIT_DOMAIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_domain_input)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True
    )
    addchat_conv = ConversationHandler(
        entry_points=[CommandHandler("addchat", addchat_start)],
        states={
            SELECT_ADD_TYPE: [CallbackQueryHandler(addchat_select_type, pattern="^addtype_")],
            AWAIT_CHAT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, addchat_receive_id)],
            AWAIT_CHAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addchat_receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    deletechat_conv = ConversationHandler(
        entry_points=[CommandHandler("deletechat", deletechat_start)],
        states={
            SELECT_CHAT_TO_DELETE: [CallbackQueryHandler(deletechat_select, pattern="^del_")],
            CONFIRM_DELETION: [CallbackQueryHandler(deletechat_confirm, pattern="^del_confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            SELECT_TARGET_CHAT: [CallbackQueryHandler(post_select_chat, pattern="^post_chat_")],
            SELECT_COMMAND: [CallbackQueryHandler(post_select_command, pattern="^post_cmd_")],
            AWAIT_COMMAND_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_handle_input)],
            AWAIT_POST_DOMAIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_handle_domain_input)],
            AWAIT_POST_COUNTRY: [CallbackQueryHandler(post_handle_country_selection, pattern="^post_country_|^post_cmd_back$")]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("freeproxyip", freeproxyip_command))
    application.add_handler(main_conv); application.add_handler(domain_conv)
    application.add_handler(addchat_conv); application.add_handler(deletechat_conv); application.add_handler(post_conv)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^country_|^pause_|^resume_|^cancel_|^freeproxy_cancel|^fmt_"))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
