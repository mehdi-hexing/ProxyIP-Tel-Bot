# In 23 Tir of 1404, this project was completed and thanks to Dìana for Free Proxy IPs.
# 10:30 AM
import os
import logging
import uuid
import asyncio
import httpx
import io
import re
import ipaddress
import json
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
WORKER_URL = "https://YourProxyIPChecker.pages.dev"

DB_FILE = "bot_data.json"
MESSAGE_ENTITY_LIMIT = 45
RISK_SCORE_URL_TEMPLATE = "https://fraundrisk.arshiaplus.com/{ip}"

AWAIT_MAIN_INPUT = 0
SELECT_ADD_TYPE, AWAIT_CHAT_ID, AWAIT_ADD_CONFIRMATION, AWAIT_CHAT_NAME = range(1, 5)
SELECT_TARGET_CHAT, SELECT_COMMAND, AWAIT_COMMAND_INPUT, AWAIT_POST_COUNTRY = range(5, 9)
SELECT_CHAT_TO_DELETE, CONFIRM_DELETION = range(9, 11)
AWAIT_DOMAIN_INPUT = 300
AWAIT_POST_DOMAIN_INPUT = 300

COUNTRIES = {
    'ALL': 'ðŸŒ All Countries', 'AE': 'ðŸ‡¦ðŸ‡ª UAE', 'AL': 'ðŸ‡¦ðŸ‡± Albania', 'AM': 'ðŸ‡¦ðŸ‡² Armenia', 'AR': 'ðŸ‡¦ðŸ‡· Argentina', 'AT': 'ðŸ‡¦ðŸ‡¹ Austria', 'AU': 'ðŸ‡¦ðŸ‡º Australia', 'AZ': 'ðŸ‡¦ðŸ‡¿ Azerbaijan', 'BE': 'ðŸ‡§ðŸ‡ª Belgium', 'BG': 'ðŸ‡§ðŸ‡¬ Bulgaria', 'BR': 'ðŸ‡§ðŸ‡· Brazil', 'CA': 'ðŸ‡¨ðŸ‡¦ Canada', 'CH': 'ðŸ‡¨ðŸ‡­ Switzerland', 'CN': 'ðŸ‡¨ðŸ‡³ China', 'CO': 'ðŸ‡¨ðŸ‡´ Colombia', 'CY': 'ðŸ‡¨ðŸ‡¾ Cyprus', 'CZ': 'ðŸ‡¨ðŸ‡¿ Czechia', 'DE': 'ðŸ‡©ðŸ‡ª Germany', 'DK': 'ðŸ‡©ðŸ‡° Denmark', 'EE': 'ðŸ‡ªðŸ‡ª Estonia', 'ES': 'ðŸ‡ªðŸ‡¸ Spain', 'FI': 'ðŸ‡«ðŸ‡® Finland', 'FR': 'ðŸ‡«ðŸ‡· France', 'GB': 'ðŸ‡¬ðŸ‡§ UK', 'GI': 'ðŸ‡¬ðŸ‡® Gibraltar', 'HK': 'ðŸ‡­ðŸ‡° Hong Kong', 'HU': 'ðŸ‡­ðŸ‡º Hungary', 'ID': 'ðŸ‡®ðŸ‡© Indonesia', 'IE': 'ðŸ‡®ðŸ‡ª Ireland', 'IL': 'ðŸ‡®ðŸ‡± Israel', 'IN': 'ðŸ‡®ðŸ‡³ India', 'IR': 'ðŸ‡®ðŸ‡· Iran', 'IT': 'ðŸ‡®ðŸ‡¹ Italy', 'JP': 'ðŸ‡¯ðŸ‡µ Japan', 'KR': 'ðŸ‡°ðŸ‡· South Korea', 'KZ': 'ðŸ‡°ðŸ‡¿ Kazakhstan', 'LT': 'ðŸ‡±ðŸ‡¹ Lithuania', 'LU': 'ðŸ‡±ðŸ‡º Luxembourg', 'LV': 'ðŸ‡±ðŸ‡» Latvia', 'MD': 'ðŸ‡²ðŸ‡© Moldova', 'MX': 'ðŸ‡²ðŸ‡½ Mexico', 'MY': 'ðŸ‡²ðŸ‡¾ Malaysia', 'NL': 'ðŸ‡³ðŸ‡± Netherlands', 'NZ': 'ðŸ‡³ðŸ‡¿ New Zealand', 'PH': 'ðŸ‡µðŸ‡­ Philippines', 'PL': 'ðŸ‡µðŸ‡± Poland', 'PR': 'ðŸ‡µðŸ‡· Puerto Rico', 'PT': 'ðŸ‡µðŸ‡¹ Portugal', 'QA': 'ðŸ‡¶ðŸ‡¦ Qatar', 'RO': 'ðŸ‡·ðŸ‡´ Romania', 'RS': 'ðŸ‡·ðŸ‡¸ Serbia', 'RU': 'ðŸ‡·ðŸ‡º Russia', 'SA': 'ðŸ‡¸ðŸ‡¦ Saudi Arabia', 'SC': 'ðŸ‡¸ðŸ‡¨ Seychelles', 'SE': 'ðŸ‡¸ðŸ‡ª Sweden', 'SG': 'ðŸ‡¸ðŸ‡¬ Singapore', 'SK': 'ðŸ‡¸ðŸ‡° Slovakia', 'TH': 'ðŸ‡¹ðŸ‡­ Thailand', 'TR': 'ðŸ‡¹ðŸ‡· Turkey', 'TW': 'ðŸ‡¹ðŸ‡¼ Taiwan', 'UA': 'ðŸ‡ºðŸ‡¦ Ukraine', 'US': 'ðŸ‡ºðŸ‡¸ USA', 'UZ': 'ðŸ‡ºðŸ‡¿ Uzbekistan', 'VN': 'ðŸ‡»ðŸ‡³ Vietnam'
}
COUNTRY_URLS = {"ALL": "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/02_proxies.csv"}
COUNTRY_FILE_BASE_URL = "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/"
NUMBER_EMOJIS = ['0ï¸âƒ£', '1ï¸âƒ£', '2ï¸âƒ£', '3ï¸âƒ£', '4ï¸âƒ£', '5ï¸âƒ£', '6ï¸âƒ£', '7ï¸âƒ£', '8ï¸âƒ£', '9ï¸âƒ£']

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

async def validate_proxy_with_worker(ip_obj: dict or str) -> dict | None:
    proxy_address = ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj
    async with httpx.AsyncClient() as client:
        try:
            params = {'proxyip': proxy_address}
            response = await client.get(f"{WORKER_URL}/api/check", params=params, timeout=45.0)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                if isinstance(ip_obj, dict):
                    data.update(ip_obj)
                return data
            return None
        except Exception as e:
            logger.error(f"Worker API Error for {proxy_address}: {e}")
            return None

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

async def _validate_and_resolve_domains(inputs: list) -> (list, str, list, dict):
    invalid_domains = []
    valid_domains = []
    for domain in inputs:
        # A new condition is added to check for 'www.'
        if domain.lower().startswith('www.') or 'http://' in domain or 'https://' in domain or '/' in domain or not re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$', domain):
            invalid_domains.append(domain)
        else:
            valid_domains.append(domain)

    if invalid_domains:
        # The error message is now in English and includes the 'www.' rule
        invalid_list = "\n".join(f"- `{d}`" for d in invalid_domains)
        error_message = (
            f"Invalid format for the following domain(s).\n"
            f"Do not include `http://`, `https://`, or `www.`.\n\n"
            f"{invalid_list}\n\n"
            f"Example of a correct format:\n"
            f"`nima.nscl.ir`"
        )
        return None, error_message, None, None

    ips_to_check, domain_map = [], {}
    async with httpx.AsyncClient() as client:
        for i, domain_item in enumerate(valid_domains):
            try:
                params = {'domain': domain_item}
                response = await client.get(f"{WORKER_URL}/api/resolve", params=params, timeout=45.0)
                response.raise_for_status()
                api_result = response.json()
                if api_result.get("success"):
                    domain_map[i] = domain_item
                    for ip in api_result.get("ips", []):
                        ips_to_check.append({"ip": ip, "domain_index": i})
            except Exception as e:
                logger.error(f"Error resolving domain {domain_item}: {e}")
    
    unique_ips_to_check = list({item['ip']: item for item in ips_to_check}.values())
    return valid_domains, None, unique_ips_to_check, domain_map

async def test_ips_and_update_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, ips_to_check: list, title: str, domain_map: dict = None, range_map: dict = None):
    test_id = str(uuid.uuid4())
    context.user_data[test_id] = {
        'status': 'running', 'ips': ips_to_check, 'checked_ips': set(),
        'successful': [], 'domain_map': domain_map, 'range_map': range_map,
        'result_message_ids': [message_id]
    }
    
    keyboard = [[
        InlineKeyboardButton("Pause", callback_data=f"pause_{test_id}"),
        InlineKeyboardButton("Cancel", callback_data=f"cancel_{test_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data[test_id]['markup'] = reply_markup

    initial_text = f"Starting test for {len(ips_to_check)} IPs..."
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=initial_text, reply_markup=reply_markup)
    except BadRequest:
        try:
            new_message = await context.bot.send_message(chat_id=chat_id, text=initial_text, reply_markup=reply_markup)
            context.user_data[test_id]['result_message_ids'] = [new_message.message_id]
        except Exception as e:
            logger.error(f"Failed to send new message: {e}")
            return
    
    context.application.create_task(process_ips_in_batches(context, chat_id, test_id, title))

async def process_ips_in_batches(context: ContextTypes.DEFAULT_TYPE, chat_id: int, test_id: str, title: str):
    try:
        test_data = context.user_data.get(test_id)
        if not test_data: return

        domain_map = test_data.get('domain_map')
        range_map = test_data.get('range_map')
        batch_size = 30
        last_sent_texts = {}
        
        async def check_and_append(ip_obj):
            ip_to_track = ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj
            test_data['checked_ips'].add(ip_to_track)
            result = await validate_proxy_with_worker(ip_obj)
            if result:
                test_data['successful'].append(result)

        while len(test_data['checked_ips']) < len(test_data['ips']):
            current_state = context.user_data.get(test_id, {}).get('status', 'stopped')
            if current_state == 'stopped': break
            if current_state == 'paused':
                await asyncio.sleep(1)
                continue

            unchecked_ip_objects = [ip_obj for ip_obj in test_data['ips'] if (ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj) not in test_data['checked_ips']]
            batch = unchecked_ip_objects[:batch_size]
            if not batch:
                logger.warning(f"Test {test_id} stalled. Breaking loop.")
                break
                
            await asyncio.gather(*(check_and_append(ip_obj) for ip_obj in batch))
            
            messages_to_send = []
            current_parts = []
            
            for overall_idx, res in enumerate(test_data['successful']):
                if not current_parts:
                    page_index = len(messages_to_send)
                    is_first_page = (page_index == 0)
                    current_title = title if is_first_page else f"**Continuation {title.strip('**')}**"
                    header = f"Checked: {len(test_data['checked_ips'])}/{len(test_data['ips'])} | Successful: {len(test_data['successful'])}"
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

                # --- Start of modifications ---

                ping_value = res.get('ping')
                # Create the ping string with a leading separator, if ping exists.
                ping_str = f" - Ping : {ping_value} ms" if ping_value is not None else ""

                # Key change: Inject the ping string directly into the details parentheses.
                details = f"({geo_info.get('country', 'N/A')} - {as_name}{ping_str})"
                
                proxy_ip_for_url = res.get('proxyIP').split(':')[0].replace('[','').replace(']','')
                risk_link = RISK_SCORE_URL_TEMPLATE.format(ip=proxy_ip_for_url)

                # Assemble the final output lines.
                line1 = f"{number_emoji} {res.get('proxyIP')} {details}"
                line2 = f"risk and score: {risk_link}"

                full_content_for_block = f"{line1}\n{line2}"
                new_line = f"```{full_content_for_block}```"

                # --- End of modifications ---
                
                if len("\n".join(current_parts)) + len(new_line) + 2 > 4000: # +2 for newlines
                    messages_to_send.append("\n".join(current_parts))
                    header = f"Checked: {len(test_data['checked_ips'])}/{len(test_data['ips'])} | Successful: {len(test_data['successful'])}"
                    current_parts = [f"**Continuation {title.strip('**')}**", header, "---", new_line]
                else:
                    current_parts.append(new_line)

            if current_parts:
                messages_to_send.append("\n".join(current_parts))

            for i, text_content in enumerate(messages_to_send):
                try:
                    last_sent_texts[i] = text_content
                    is_first_message = (i == 0)
                    current_markup = test_data.get('markup') if is_first_message else None
                    if i >= len(test_data['result_message_ids']):
                        new_msg = await context.bot.send_message(chat_id=chat_id, text=text_content, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup, disable_web_page_preview=True)
                        test_data['result_message_ids'].append(new_msg.message_id)
                    else:
                        message_id = test_data['result_message_ids'][i]
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_content, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup, disable_web_page_preview=True)
                except BadRequest as e:
                    if "Message is not modified" not in str(e): logger.warning(f"Update failed for message page {i}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error during update for message page {i}: {e}")

            await asyncio.sleep(1.5)

        status = "Cancelled" if context.user_data.get(test_id, {}).get('status') == 'stopped' else "Completed"
        
        for i, message_id in enumerate(test_data['result_message_ids']):
            try:
                final_text = last_sent_texts.get(i)
                if not final_text:
                    continue

                if f"Test {status}" not in final_text:
                    final_text += f"\n\n**Test {status}.**"
                if i == 0 and not test_data['successful']:
                     final_text = f"**{title}**\nNo successful proxies found.\n\n**Test {status}.**"

                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode=ParseMode.MARKDOWN, reply_markup=None, disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Error during finalization of message {message_id}: {e}")

        if test_data['successful']:
            final_sorted_ips = sorted([res['proxyIP'] for res in test_data['successful']], key=lambda ip: ipaddress.ip_address(ip.split(':')[0].replace('[','').replace(']','')))
            copy_text = "\n".join(final_sorted_ips)
            await context.bot.send_message(chat_id=chat_id, text=f"To copy all IPs, tap the code block below:\n```\n{copy_text}\n```", parse_mode=ParseMode.MARKDOWN_V2)

            file_name = f"successful_proxies_{uuid.uuid4().hex[:6]}"
            txt_file = io.BytesIO(copy_text.encode('utf-8'))
            await context.bot.send_document(chat_id=chat_id, document=txt_file, filename=f"{file_name}.txt")
            csv_file = io.BytesIO(copy_text.encode('utf-8'))
            await context.bot.send_document(chat_id=chat_id, document=csv_file, filename=f"{file_name}.csv")
            
    finally:
        if test_id in context.user_data: del context.user_data[test_id]

async def run_test_and_post(context: ContextTypes.DEFAULT_TYPE, target_chat_id, ips_to_check: list, title: str, confirmation_message, domain_map: dict = None, range_map: dict = None):
    try:
        successful_results_with_info = []
        batch_size = 30
        for i in range(0, len(ips_to_check), batch_size):
            batch = ips_to_check[i:i + batch_size]
            
            results = await asyncio.gather(*(validate_proxy_with_worker(ip_obj) for ip_obj in batch))
            
            successful_results_with_info.extend([res for res in results if res])
            await asyncio.sleep(1)

        if not successful_results_with_info:
            await context.bot.send_message(chat_id=target_chat_id, text=f"**{title}**\nNo successful proxies found.", parse_mode=ParseMode.MARKDOWN)
            return

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
            if len(as_name) > 70:
                as_name = as_name[:67] + '...'

            # --- Start of modifications ---

            ping_value = res.get('ping')
            # Create the ping string with a leading separator, if ping exists.
            ping_str = f" - Ping : {ping_value} ms" if ping_value is not None else ""
            
            # Key change: Inject the ping string directly into the details parentheses.
            details = f"({geo_info.get('country', 'N/A')} - {as_name}{ping_str})"
            
            proxy_ip_for_url = res.get('proxyIP').split(':')[0].replace('[','').replace(']','')
            risk_link = RISK_SCORE_URL_TEMPLATE.format(ip=proxy_ip_for_url)

            # Assemble the final output lines.
            line1 = f"{number_emoji} {res.get('proxyIP')} {details}"
            line2 = f"risk and score: {risk_link}"
            
            full_content_for_block = f"{line1}\n{line2}"
            new_line = f"```{full_content_for_block}```"

            # --- End of modifications ---

            if len("\n".join(message_parts)) + len(new_line) + 2 > TELEGRAM_MESSAGE_LIMIT:
                await context.bot.send_message(chat_id=target_chat_id, text="\n".join(message_parts), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                await asyncio.sleep(0.5)
                
                message_count += 1
                new_title = f"**Continuation {title.strip('**')}**"
                message_parts = [new_title, "---", new_line]
            else:
                message_parts.append(new_line)

        if message_parts:
            message_parts.append("\n**Test Completed.**")
            final_message_text = "\n".join(message_parts)
            await context.bot.send_message(chat_id=target_chat_id, text=final_message_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            await asyncio.sleep(0.5)

        final_sorted_ips = sorted([res['proxyIP'] for res in successful_results_with_info], key=lambda ip: ipaddress.ip_address(ip.split(':')[0].replace('[','').replace(']','')))
        copy_text = "\n".join(final_sorted_ips)
        
        await context.bot.send_message(chat_id=target_chat_id, text=f"To copy all IPs, tap the code block below:\n```\n{copy_text}\n```", parse_mode=ParseMode.MARKDOWN_V2)
        
        file_name = f"successful_proxies_{uuid.uuid4().hex[:6]}"
        txt_file = io.BytesIO(copy_text.encode('utf-8'))
        await context.bot.send_document(chat_id=target_chat_id, document=txt_file, filename=f"{file_name}.txt")
        csv_file = io.BytesIO(copy_text.encode('utf-8'))
        await context.bot.send_document(chat_id=target_chat_id, document=csv_file, filename=f"{file_name}.csv")

    except Exception as e:
        logger.error(f"Error in run_test_and_post: {e}")
        await context.bot.send_message(chat_id=confirmation_message.chat_id, text=f"An unexpected error occurred while posting: {e}")
    finally:
        try:
            await context.bot.delete_message(chat_id=confirmation_message.chat_id, message_id=confirmation_message.message_id)
        except Exception:
            pass
            
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("ðŸ‘‹ Welcome! Use the menu commands to start.")

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

    sent_message = await update.message.reply_text("Processing your input...")
    inputs = update.message.text.split()
    await process_command_logic(update, context, command, inputs, sent_message)
    return ConversationHandler.END

async def process_command_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str, inputs: list, message):
    chat_id, message_id = message.chat_id, message.message_id
    
    ips_with_context = []
    if command == "proxyip":
        ips_with_context = [{"ip": ip} for ip in inputs]
        await test_ips_and_update_message(context, chat_id, message_id, ips_with_context, "Proxy IP Results")
    elif command == "iprange":
        range_map = {}
        for i, range_str in enumerate(inputs):
            range_map[i] = range_str
            for ip in parse_ip_range(range_str):
                ips_with_context.append({"ip": ip, "range_index": i})

        title_header = "**Results for IP Range(s):**"
        title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in range_map.items()]
        title = f"{title_header}\n" + "\n".join(title_parts)

        if not ips_with_context:
            await message.edit_text("Invalid range format or no IPs found in range(s).")
        else:
            await test_ips_and_update_message(context, chat_id, message_id, ips_with_context, title, range_map=range_map)
    elif command == "file":
        file_url = inputs[0]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', text)))
            ips_with_context = [{"ip": ip} for ip in ips_found]
            if not ips_with_context: await message.edit_text("No valid IPs found in the file.")
            else: await test_ips_and_update_message(context, chat_id, message.message_id, ips_with_context, "File Test Results")
        except Exception as e: await message.edit_text(f"Error processing file: {e}") 

async def domain_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text(f"Please use `/domain` without mentioning the bot's name.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    if context.args:
        return await validate_and_process_domains(update, context, context.args)
    
    await update.message.reply_text(
        "Please send the domain(s) you want to check.\n"
        "To cancel at any time, send /cancel."
    )
    return AWAIT_DOMAIN_INPUT

async def handle_domain_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    inputs = update.message.text.split()
    return await validate_and_process_domains(update, context, inputs)

async def validate_and_process_domains(update: Update, context: ContextTypes.DEFAULT_TYPE, inputs: list) -> int:
    valid_domains, error_message, ips_to_check, domain_map = await _validate_and_resolve_domains(inputs)

    if error_message:
        await update.message.reply_text(
            f"{error_message}\n\nPlease send the corrected domain(s), or /cancel to quit.",
            parse_mode=ParseMode.MARKDOWN
        )
        return AWAIT_DOMAIN_INPUT

    sent_message = await update.message.reply_text(f"Resolving {len(valid_domains)} domain(s)...")

    if len(valid_domains) > 1:
        title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in domain_map.items()]
        title = "**Results for Domains:**\n" + "\n".join(title_parts)
    else:
        title = f"**Results for:** `{valid_domains[0]}`"

    if not ips_to_check:
        await sent_message.edit_text("Could not resolve any IPs from the provided domains.")
    else:
        await test_ips_and_update_message(context, sent_message.chat_id, sent_message.message_id, ips_to_check, title, domain_map=domain_map)
    
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
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="freeproxy_cancel")])
    await update.message.reply_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))

async def addchat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("To use this command, please send it to me in a private chat.")
        return ConversationHandler.END
        
    keyboard = [[
        InlineKeyboardButton("Group", callback_data="addtype_group"),
        InlineKeyboardButton("Channel", callback_data="addtype_channel")
    ]]
    await update.message.reply_text("Which do you want to add?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_ADD_TYPE

async def addchat_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chat_type = query.data.split('_')[-1]
    context.user_data['add_chat_type'] = chat_type
    if chat_type == 'channel':
        prompt = "Please send the channel username (e.g., @mychannel)."
    else:
        prompt = "Please send the group's numerical ID. \nIf you don't know it, use @userinfobot: forward a message from your group to this bot to get the ID (it starts with -100...)."
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
                await waiting_message.edit_text("Error: âŒ\nThe bot is not an administrator in this channel or lacks permission to post messages. Please grant the necessary admin rights first.")
                return ConversationHandler.END
        elif chat_type == 'group':
            if bot_member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await waiting_message.edit_text("Error: âŒ\nThe bot is not a member of this group. Please add the bot to the group first.")
                return ConversationHandler.END

        user_member = await context.bot.get_chat_member(chat_id=chat_id_str, user_id=user_id)
        if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await waiting_message.edit_text("Error: âŒ\nYou must be an administrator or owner of this chat to register it.")
            return ConversationHandler.END

        target_chat = await context.bot.get_chat(chat_id=chat_id_str)
        context.user_data['new_chat_id'] = target_chat.id
        context.user_data['new_chat_title'] = target_chat.title

        await waiting_message.edit_text(
            f"âœ… Successfully verified chat '{target_chat.title}'!\n\n"
            "Please send a custom name for this destination now."
        )
        return AWAIT_CHAT_NAME

    except BadRequest as e:
        if "chat not found" in e.message.lower():
            await waiting_message.edit_text("Error: Chat not found. Please check the ID or username and ensure the bot has been added to the chat.")
        else:
            await waiting_message.edit_text(f"Verification error: {e.message}")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in addchat_receive_id: {e}")
        await waiting_message.edit_text("An unexpected error occurred during verification.")
        return ConversationHandler.END

async def addchat_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_str = str(update.message.from_user.id)
    name = update.message.text
    chat_id = context.user_data.pop('new_chat_id', None)
    
    if not chat_id:
        await update.message.reply_text("Something went wrong. Please start over with /addchat.")
        context.user_data.clear()
        return ConversationHandler.END
    
    db = load_db()
    user_chats = db.get(user_id_str, [])
        
    if not any(c['chat_id'] == chat_id for c in user_chats):
        user_chats.append({"chat_id": chat_id, "name": name})
        db[user_id_str] = user_chats
        save_db(db)
        await update.message.reply_text(f"âœ… Destination '{name}' was successfully registered!")
    else:
        await update.message.reply_text("This chat has already been registered.")
        
    context.user_data.clear()
    return ConversationHandler.END

async def deletechat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("To use this command, please send it to me in a private chat.")
        return ConversationHandler.END

    user_chats = load_db().get(str(update.message.from_user.id), [])
    if not user_chats:
        await update.message.reply_text("You have no saved chats to delete.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(chat['name'], callback_data=f"del_chat_{chat['chat_id']}")] for chat in user_chats]
    keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="del_cancel")])
    await update.message.reply_text("Select a destination to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_CHAT_TO_DELETE

async def deletechat_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "del_cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    context.user_data['chat_to_delete'] = query.data.split('_')[-1]
    keyboard = [[InlineKeyboardButton("âœ… Yes, delete it", callback_data="del_confirm_yes"), InlineKeyboardButton("âŒ No, go back", callback_data="del_confirm_no")]]
    await query.edit_message_text(f"Are you sure you want to delete this destination?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_DELETION

async def deletechat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id_str = str(query.from_user.id)
    db = load_db()
    
    if query.data == "del_confirm_no":
        user_chats = db.get(user_id_str, [])
        keyboard = [[InlineKeyboardButton(chat['name'], callback_data=f"del_chat_{chat['chat_id']}")] for chat in user_chats]
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="del_cancel")])
        await query.edit_message_text("Select a destination to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_CHAT_TO_DELETE

    chat_id_to_delete = context.user_data.pop('chat_to_delete', None)
    user_chats = db.get(user_id_str, [])
    updated_chats = [chat for chat in user_chats if str(chat['chat_id']) != str(chat_id_to_delete)]
    
    if len(updated_chats) < len(user_chats):
        db[user_id_str] = updated_chats
        save_db(db)
        await query.edit_message_text("âœ… Destination successfully deleted.")
    else:
        await query.edit_message_text("Could not find the destination to delete.")
    return ConversationHandler.END

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("To use this command, please send it to me in a private chat.")
        return ConversationHandler.END

    user_chats = load_db().get(str(update.message.from_user.id), [])
    if not user_chats:
        await update.message.reply_text("You haven't added any destinations yet. Use /addchat to add one first.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(chat['name'], callback_data=f"post_chat_{chat['chat_id']}")] for chat in user_chats]
    await update.message.reply_text("Please select a destination to post the results:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_TARGET_CHAT

async def post_select_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['target_chat_id'] = query.data.split('_')[-1]
    keyboard = [
        [InlineKeyboardButton("Proxy IP Test", callback_data="post_cmd_proxyip")],
        [InlineKeyboardButton("IP Range Test", callback_data="post_cmd_iprange")],
        [InlineKeyboardButton("Domain Test", callback_data="post_cmd_domain")],
        [InlineKeyboardButton("File URL Test", callback_data="post_cmd_file")],
        [InlineKeyboardButton("âœ¨ Free Proxies by Country", callback_data="post_cmd_freeproxyip")],
    ]
    await query.edit_message_text("Now, select the type of test:", reply_markup=InlineKeyboardMarkup(keyboard))
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
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="post_cmd_back")])
        await query.edit_message_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))
        return AWAIT_POST_COUNTRY
    elif command == 'domain':
        await query.edit_message_text(f"Great! Now please send the input for the `{command}` command.", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_POST_DOMAIN_INPUT
    else:
        await query.edit_message_text(f"Great! Now please send the input for the `{command}` command.", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_COMMAND_INPUT

async def post_handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_chat_id_str, command = context.user_data.get('target_chat_id'), context.user_data.get('post_command')
    if not target_chat_id_str: return ConversationHandler.END
    
    confirmation_message = await update.message.reply_text("âœ… Request received. The test will run in the background. Final results will be posted shortly...")
    inputs = update.message.text.split()
    context.application.create_task(run_post_command_logic(context, target_chat_id_str, command, inputs, confirmation_message))
    context.user_data.clear()
    return ConversationHandler.END

async def post_handle_domain_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    inputs = update.message.text.split()
    valid_domains, error_message, _, _ = await _validate_and_resolve_domains(inputs)
    
    if error_message:
        await update.message.reply_text(f"{error_message}\n\nPlease send the corrected domain(s), or /cancel to quit.", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_POST_DOMAIN_INPUT

    target_chat_id_str, command = context.user_data.get('target_chat_id'), context.user_data.get('post_command')
    if not target_chat_id_str: return ConversationHandler.END

    confirmation_message = await update.message.reply_text("âœ… Request received. The test will run in the background. Final results will be posted shortly...")
    context.application.create_task(run_post_command_logic(context, target_chat_id_str, command, valid_domains, confirmation_message))
    context.user_data.clear()
    return ConversationHandler.END

async def post_handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "post_cmd_back":
        keyboard = [[InlineKeyboardButton("Proxy IP Test", callback_data="post_cmd_proxyip")], [InlineKeyboardButton("IP Range Test", callback_data="post_cmd_iprange")], [InlineKeyboardButton("Domain Test", callback_data="post_cmd_domain")], [InlineKeyboardButton("File URL Test", callback_data="post_cmd_file")], [InlineKeyboardButton("âœ¨ Free Proxies by Country", callback_data="post_cmd_freeproxyip")]]
        await query.edit_message_text("Now, select the type of test:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_COMMAND

    target_chat_id_str, country_code = context.user_data.get('target_chat_id'), query.data.split('_')[-1]
    if not target_chat_id_str: return ConversationHandler.END

    country_name_full = COUNTRIES.get(country_code, "Selected Country")
    confirmation_message = await query.edit_message_text(f"âœ… Request received for {country_name_full}. The results will be posted shortly.")
    context.application.create_task(run_post_command_logic(context, target_chat_id_str, "freeproxyip", [country_code], confirmation_message, title_prefix=f"**{country_name_full} Test Results**"))
    context.user_data.clear()
    return ConversationHandler.END

async def run_post_command_logic(context: ContextTypes.DEFAULT_TYPE, target_chat_id_str: str, command: str, inputs: list, confirmation_message, title_prefix: str = ""):
    ips_to_check, domain_map, range_map, title = [], {}, {}, title_prefix
    try:
        target_chat_id = int(target_chat_id_str) if target_chat_id_str.startswith('-') else target_chat_id_str
    except ValueError:
        target_chat_id = target_chat_id_str

    try:
        if command == "proxyip":
            ips_to_check = [{"ip": ip} for ip in inputs]
            title = title or "Proxy IP Test Results:"
        elif command == "iprange":
            for i, r in enumerate(inputs):
                range_map[i] = r
                for ip in parse_ip_range(r):
                    ips_to_check.append({"ip": ip, "range_index": i})
            
            title_header = "**Results for IP Range(s):**"
            title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in range_map.items()]
            title = f"{title_header}\n" + "\n".join(title_parts)
        elif command == "domain":
            _, _, ips_to_check, domain_map = await _validate_and_resolve_domains(inputs)
            
            title_header = "**Results for:**"
            title_parts = []
            TITLE_CHAR_LIMIT = 1500
            current_len = len(title_header) + 1

            for i, name in domain_map.items():
                part = f"{format_number_with_emojis(i+1)} `{name}`"
                if current_len + len(part) + 1 > TITLE_CHAR_LIMIT:
                    title_parts.append("...")
                    break
                title_parts.append(part)
                current_len += len(part) + 1
            
            title = f"{title_header}\n" + "\n".join(title_parts)
        elif command == "file":
            async with httpx.AsyncClient() as client:
                response = await client.get(inputs[0], timeout=15)
                response.raise_for_status()
                ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', response.text)))
                ips_to_check = [{"ip": ip} for ip in ips_found]
            title = title or "File Test Results:"
        elif command == "freeproxyip":
            country_code = inputs[0]
            url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                response.raise_for_status()
                ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', response.text)))
                ips_to_check = [{"ip": ip} for ip in ips_found]
            title = title_prefix or f"{COUNTRIES.get(country_code)} Test Results:"
                
        if not ips_to_check:
            await context.bot.send_message(chat_id=target_chat_id, text="No valid IPs found from your input to test.")
            await context.bot.delete_message(chat_id=confirmation_message.chat_id, message_id=confirmation_message.message_id)
            return
            
        await run_test_and_post(context, target_chat_id, ips_to_check, title, confirmation_message, domain_map, range_map)
    except Exception as e:
        logger.error(f"Error in post preparation: {e}")
        await context.bot.send_message(chat_id=confirmation_message.chat_id, text=f"An error occurred during post operation: {e}")
        try: await context.bot.delete_message(chat_id=confirmation_message.chat_id, message_id=confirmation_message.message_id)
        except Exception: pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split('_', 1)
    callback_type, data = parts[0], (parts[1] if len(parts) > 1 else None)
    
    pause_message = "\n\n**Operation paused. Click Resume to continue.**"

    if callback_type == "freeproxy" and data == "cancel":
        await query.answer()
        await query.edit_message_text("Operation cancelled.")
        return

    if callback_type == "country":
        await query.answer()
        country_code = data
        country_name_full = COUNTRIES.get(country_code, "Selected Country")
        url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
        sent_message = await query.edit_message_text(text=f"Fetching IPs for {country_name_full}...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_found = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', text)))
            ips_with_context = [{"ip": ip} for ip in ips_found]
            if not ips_with_context: await sent_message.edit_message_text(f"No IPs found for {country_name_full}.")
            else: await test_ips_and_update_message(context, query.message.chat_id, sent_message.message_id, ips_with_context, f"**{country_name_full} Test Results**")
        except Exception as e: await sent_message.edit_message_text(f"Error getting proxies for {country_name_full}: {e}")
        return

    test_id = data
    if not test_id or test_id not in context.user_data:
        await query.answer("This test has expired or is invalid.", show_alert=True)
        try: await query.edit_message_reply_markup(reply_markup=None)
        except BadRequest: pass
        return

    if context.user_data[test_id].get('is_modifying_state', False):
        await query.answer("Processing previous request. Please wait.")
        return
    context.user_data[test_id]['is_modifying_state'] = True

    try:
        current_status = context.user_data[test_id].get('status')

        if callback_type == 'pause':
            if current_status == 'paused':
                await query.answer("The test is already paused.")
                return
            
            await query.answer()
            context.user_data[test_id]['status'] = 'paused'
            keyboard = [[InlineKeyboardButton("Resume", callback_data=f"resume_{test_id}"), InlineKeyboardButton("Cancel", callback_data=f"cancel_{test_id}")]]
            context.user_data[test_id]['markup'] = InlineKeyboardMarkup(keyboard)
            
            current_text = query.message.text_markdown
            if pause_message not in current_text:
                try:
                    await query.edit_message_text(
                        text=f"{current_text}{pause_message}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        logger.warning(f"Failed to edit message for pause: {e}")

        elif callback_type == 'resume':
            if current_status == 'running':
                await query.answer("The test is already running.")
                return

            await query.answer()
            context.user_data[test_id]['status'] = 'running'
            keyboard = [[InlineKeyboardButton("Pause", callback_data=f"pause_{test_id}"), InlineKeyboardButton("Cancel", callback_data=f"cancel_{test_id}")]]
            context.user_data[test_id]['markup'] = InlineKeyboardMarkup(keyboard)
            
            current_text = query.message.text_markdown
            if pause_message in current_text:
                new_text = current_text.replace(pause_message, "")
                try:
                    await query.edit_message_text(
                        text=new_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        logger.warning(f"Failed to edit message for resume: {e}")

        elif callback_type == 'cancel':
            await query.answer()
            context.user_data[test_id]['status'] = 'stopped'
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except BadRequest:
                pass
    finally:
        if context.user_data.get(test_id):
            context.user_data[test_id]['is_modifying_state'] = False

async def post_init(application: Application):
    commands = [
        BotCommand("start", "ðŸ¤– Start Using Bot"),
        BotCommand("proxyip", "ðŸ” Check Proxy IPs"),
        BotCommand("iprange", "ðŸ” Check Proxy IP Ranges"),
        BotCommand("domain", "ðŸ” Resolving Domains"),
        BotCommand("file", "ðŸ” Check Proxy IPs From a File URL"),
        BotCommand("freeproxyip", "âœ¨ Get Free Proxies By Country"),
        BotCommand("addchat", "âž• Register a Channel/Group"),
        BotCommand("deletechat", "ðŸ—‘ï¸ Delete a Registered Channel/Group"),
        BotCommand("post", "ðŸš€ Post Results To a Chat"),
        BotCommand("cancel", "âŒ Cancel Current Operation"),
    ]
    await application.bot.set_my_commands(commands)
    application.create_task(run_periodic_cleanup(application))
    
def main() -> None:
    cprint("made with â¤ï¸â€ðŸ”¥ by @mehdiasmart", "light_cyan")
    
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    simple_command_list = ["proxyip", "iprange", "file"]
    
    main_conv_handler = ConversationHandler(
        entry_points=[CommandHandler(cmd, start_main_conversation) for cmd in simple_command_list],
        states={
            AWAIT_MAIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_conversation_input)],
        },
        fallbacks=[
            CommandHandler("domain", domain_start),
            CommandHandler("cancel", cancel_conversation),
        ],
        allow_reentry=True
    )

    domain_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("domain", domain_start)],
        states={
            AWAIT_DOMAIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_domain_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True
    )
    
    addchat_handler = ConversationHandler(
        entry_points=[CommandHandler("addchat", addchat_start)],
        states={
            SELECT_ADD_TYPE: [CallbackQueryHandler(addchat_select_type, pattern="^addtype_")],
            AWAIT_CHAT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, addchat_receive_id)],
            AWAIT_CHAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addchat_receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    deletechat_handler = ConversationHandler(
        entry_points=[CommandHandler("deletechat", deletechat_start)],
        states={
            SELECT_CHAT_TO_DELETE: [CallbackQueryHandler(deletechat_select, pattern="^del_")],
            CONFIRM_DELETION: [CallbackQueryHandler(deletechat_confirm, pattern="^del_confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    post_handler = ConversationHandler(
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
    application.add_handler(main_conv_handler)
    application.add_handler(domain_conv_handler)
    application.add_handler(addchat_handler)
    application.add_handler(deletechat_handler)
    application.add_handler(post_handler)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^country_|^pause_|^resume_|^cancel_|^freeproxy_cancel$"))
    application.add_handler(CommandHandler("cancel", cancel_conversation))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
