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
from telegram.constants import ParseMode, ChatType
from telegram.error import BadRequest
from termcolor import cprint

# --- Initial Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Constants ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WORKER_URL = "https://YourProxyIPChecker.pages.dev"
DB_FILE = "bot_data.json"
MESSAGE_ENTITY_LIMIT = 45

# Conversation states
AWAIT_MAIN_INPUT = 0
SELECT_ADD_TYPE, AWAIT_CHAT_ID, AWAIT_ADD_CONFIRMATION, AWAIT_CHAT_NAME = range(1, 5)
SELECT_TARGET_CHAT, SELECT_COMMAND, AWAIT_COMMAND_INPUT, AWAIT_POST_COUNTRY = range(5, 9)
SELECT_CHAT_TO_DELETE, CONFIRM_DELETION = range(9, 11)
AWAIT_DOMAIN_INPUT = 11

COUNTRIES = {
    'ALL': '🌍 All Countries', 'AE': '🇦🇪 UAE', 'AL': '🇦🇱 Albania', 'AM': '🇦🇲 Armenia', 'AR': '🇦🇷 Argentina', 'AT': '🇦🇹 Austria', 'AU': '🇦🇺 Australia', 'AZ': '🇦🇿 Azerbaijan', 'BE': '🇧🇪 Belgium', 'BG': '🇧🇬 Bulgaria', 'BR': '🇧🇷 Brazil', 'CA': '🇨🇦 Canada', 'CH': '🇨🇭 Switzerland', 'CN': '🇨🇳 China', 'CO': '🇨🇴 Colombia', 'CY': '🇨🇾 Cyprus', 'CZ': '🇨🇿 Czechia', 'DE': '🇩🇪 Germany', 'DK': '🇩🇰 Denmark', 'EE': '🇪🇪 Estonia', 'ES': '🇪🇸 Spain', 'FI': '🇫🇮 Finland', 'FR': '🇫🇷 France', 'GB': '🇬🇧 UK', 'GI': '🇬🇮 Gibraltar', 'HK': '🇭🇰 Hong Kong', 'HU': '🇭🇺 Hungary', 'ID': '🇮🇩 Indonesia', 'IE': '🇮🇪 Ireland', 'IL': '🇮🇱 Israel', 'IN': '🇮🇳 India', 'IR': '🇮🇷 Iran', 'IT': '🇮🇹 Italy', 'JP': '🇯🇵 Japan', 'KR': '🇰🇷 South Korea', 'KZ': '🇰🇿 Kazakhstan', 'LT': '🇱🇹 Lithuania', 'LU': '🇱🇺 Luxembourg', 'LV': '🇱🇻 Latvia', 'MD': '🇲🇩 Moldova', 'MX': '🇲🇽 Mexico', 'MY': '🇲🇾 Malaysia', 'NL': '🇳🇱 Netherlands', 'NZ': '🇳🇿 New Zealand', 'PH': '🇵🇭 Philippines', 'PL': '🇵🇱 Poland', 'PR': '🇵🇷 Puerto Rico', 'PT': '🇵🇹 Portugal', 'QA': '🇶🇦 Qatar', 'RO': '🇷🇴 Romania', 'RS': '🇷🇸 Serbia', 'RU': '🇷🇺 Russia', 'SA': '🇸🇦 Saudi Arabia', 'SC': '🇸🇨 Seychelles', 'SE': '🇸🇪 Sweden', 'SG': '🇸🇬 Singapore', 'SK': '🇸🇰 Slovakia', 'TH': '🇹🇭 Thailand', 'TR': '🇹🇷 Turkey', 'TW': '🇹🇼 Taiwan', 'UA': '🇺🇦 Ukraine', 'US': '🇺🇸 USA', 'UZ': '🇺🇿 Uzbekistan', 'VN': '🇻🇳 Vietnam'
}
COUNTRY_URLS = {"ALL": "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/02_proxies.csv"}
COUNTRY_FILE_BASE_URL = "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/"
NUMBER_EMOJIS = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']

# --- Database & Helper Functions ---
def load_db():
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

async def fetch_from_api(endpoint: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{WORKER_URL}/api/{endpoint}", params=params, timeout=45.0)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"API request failed for {endpoint}: {e}")
            return {"success": False, "error": f"Network error: {e.__class__.__name__}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred during API fetch: {e}")
            return {"success": False, "error": "An unexpected error occurred."}

def parse_ip_range(range_str: str) -> list[str]:
    ips = []
    try:
        if '/' in range_str and (range_str.endswith('/24') or range_str.endswith('/16') or range_str.endswith('/8')):
             net = ipaddress.ip_network(range_str, strict=False)
             if net.num_addresses > 65536:
                 logger.warning(f"IP range too large, skipping: {range_str}")
                 return []
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
    elif range_map and 'range_index' in res and res['range_index' in res] and res['range_index'] in range_map:
        prefix = f"{format_number_with_emojis(res['range_index'] + 1)} "
    return prefix

# --- Live Testing Logic ---
async def test_ips_and_update_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, ips_to_check: list, title: str, domain_map: dict = None, range_map: dict = None):
    test_id = str(uuid.uuid4())
    context.user_data[test_id] = {
        'status': 'running', 'ips': ips_to_check, 'checked_ips': set(),
        'successful': [], 'domain_map': domain_map, 'range_map': range_map,
        'result_message_ids': [message_id]
    }
    
    keyboard = [[
        InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{test_id}"),
        InlineKeyboardButton("⏹️ Cancel", callback_data=f"cancel_{test_id}")
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
            logger.error(f"Failed to send new message to {chat_id}: {e}")
            return
    
    context.application.create_task(process_ips_in_batches(context, chat_id, test_id, title))

async def process_ips_in_batches(context: ContextTypes.DEFAULT_TYPE, chat_id: int, test_id: str, title: str):
    try:
        test_data = context.user_data.get(test_id)
        if not test_data: return

        domain_map = test_data.get('domain_map')
        range_map = test_data.get('range_map')
        batch_size = 30
        last_update_texts = {}

        while len(test_data['checked_ips']) < len(test_data['ips']):
            current_state = context.user_data.get(test_id, {}).get('status', 'stopped')
            if current_state == 'stopped': break
            if current_state == 'paused':
                await asyncio.sleep(1)
                continue

            unchecked_ip_objects = [ip_obj for ip_obj in test_data['ips'] if (ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj) not in test_data['checked_ips']]
            batch = unchecked_ip_objects[:batch_size]
            
            async def check_ip(ip_obj):
                ip_to_check = ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj
                test_data['checked_ips'].add(ip_to_check)
                check_result = await fetch_from_api("check", {"proxyip": ip_to_check})
                if check_result and check_result.get("success"):
                    if isinstance(ip_obj, dict):
                        if 'domain_index' in ip_obj: check_result['domain_index'] = ip_obj['domain_index']
                        if 'range_index' in ip_obj: check_result['range_index'] = ip_obj['range_index']
                    return check_result
                return None

            results = await asyncio.gather(*(check_ip(ip_obj) for ip_obj in batch))
            
            newly_successful = [res for res in results if res]
            if newly_successful: test_data['successful'].extend(newly_successful)
            
            # Create a temporary list sorted by risk for live display
            display_sorted_list = sorted(test_data['successful'], key=lambda x: x.get('risk', {}).get('score', 999))
            
            successful_chunks = [display_sorted_list[i:i + MESSAGE_ENTITY_LIMIT] for i in range(0, len(display_sorted_list), MESSAGE_ENTITY_LIMIT)]

            for i, chunk in enumerate(successful_chunks):
                is_first_message = (i == 0)
                current_title = title if is_first_message else f"**Continuation {title.strip('**')}**"
                
                header = f"Checked: {len(test_data['checked_ips'])}/{len(test_data['ips'])} | Successful: {len(test_data['successful'])}"
                message_parts = [f"**{current_title}**", header, "---"]

                for res_index, res in enumerate(chunk):
                    overall_successful_index = i * MESSAGE_ENTITY_LIMIT + res_index
                    smart_prefix = get_result_source_prefix(res, domain_map, range_map)
                    number_emoji = smart_prefix.strip() if smart_prefix else format_number_with_emojis(overall_successful_index + 1)
                    
                    risk_info = res.get('risk', {})
                    risk_text = f"{risk_info.get('emoji', '')} {risk_info.get('level', 'N/A')} ({risk_info.get('score', 'N/A')})"
                    
                    geo_info = res.get('info', {})
                    details = f"({geo_info.get('country', 'N/A')} - {geo_info.get('as', 'N/A')})"
                    ip_info = f"{res.get('proxyIP')} {details}\n{risk_text}"
                    message_parts.append(f"```{number_emoji}\n{ip_info}```")
                
                reply_text = "\n".join(message_parts)

                if i >= len(test_data['result_message_ids']):
                    try:
                        new_msg = await context.bot.send_message(chat_id=chat_id, text=reply_text, parse_mode=ParseMode.MARKDOWN)
                        test_data['result_message_ids'].append(new_msg.message_id)
                        last_update_texts[new_msg.message_id] = reply_text
                    except Exception as e:
                        logger.error(f"Failed to send continuation message: {e}")
                        continue
                
                message_id_to_edit = test_data['result_message_ids'][i]
                if reply_text != last_update_texts.get(message_id_to_edit):
                    try:
                        current_markup = test_data.get('markup') if is_first_message else None
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=reply_text, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup)
                        last_update_texts[message_id_to_edit] = reply_text
                    except BadRequest as e:
                        if "Message is not modified" not in str(e): logger.warning(f"Failed to edit message {message_id_to_edit}: {e}")

            await asyncio.sleep(1)

        status = "Cancelled" if context.user_data.get(test_id, {}).get('status') == 'stopped' else "Completed"
        
        for i, message_id in enumerate(test_data['result_message_ids']):
            final_text = last_update_texts.get(message_id, "")
            if i == len(test_data['result_message_ids']) - 1: final_text += f"\n\n**Test {status}.**"
            if not test_data['successful'] and i == 0: final_text = f"**{title}**\nNo successful proxies found."
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode=ParseMode.MARKDOWN, reply_markup=None)
            except BadRequest as e:
                if "Message is not modified" not in str(e): logger.warning(f"Failed to finalize message {message_id}: {e}")

        if test_data['successful']:
            # Sort final list by IP address for copy/file output
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

# --- Background Task Logic (for /post) ---
async def run_test_and_post(context: ContextTypes.DEFAULT_TYPE, target_chat_id, ips_to_check: list, title: str, confirmation_message, domain_map: dict = None, range_map: dict = None):
    try:
        successful_results_with_info = []
        batch_size = 30
        for i in range(0, len(ips_to_check), batch_size):
            batch = ips_to_check[i:i + batch_size]
            async def check_ip_and_add_context(ip_obj):
                ip_to_check = ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj
                check_result = await fetch_from_api("check", {"proxyip": ip_to_check})
                if check_result and check_result.get("success"):
                    if isinstance(ip_obj, dict):
                        if 'domain_index' in ip_obj: check_result['domain_index'] = ip_obj['domain_index']
                        if 'range_index' in ip_obj: check_result['range_index'] = ip_obj['range_index']
                    return check_result
                return None

            results = await asyncio.gather(*(check_ip_and_add_context(ip) for ip in batch))
            successful_results_with_info.extend([res for res in results if res])
            await asyncio.sleep(1)

        if not successful_results_with_info:
            await context.bot.send_message(chat_id=target_chat_id, text=f"**{title}**\nNo successful proxies found.", parse_mode=ParseMode.MARKDOWN)
            return

        # Sort the list for display purposes by risk score
        display_sorted_list = sorted(successful_results_with_info, key=lambda x: x.get('risk', {}).get('score', 999))
        
        successful_chunks = [display_sorted_list[i:i + MESSAGE_ENTITY_LIMIT] for i in range(0, len(display_sorted_list), MESSAGE_ENTITY_LIMIT)]
        
        for i, chunk in enumerate(successful_chunks):
            is_first_message = (i == 0)
            current_title = title if is_first_message else f"**Continuation {title.strip('**')}**"
            message_parts = [f"**{current_title}**", "---"]
            
            for res_index, res in enumerate(chunk):
                overall_successful_index = i * MESSAGE_ENTITY_LIMIT + res_index
                smart_prefix = get_result_source_prefix(res, domain_map, range_map)
                number_emoji = smart_prefix.strip() if smart_prefix else format_number_with_emojis(overall_successful_index + 1)
                
                risk_info = res.get('risk', {})
                risk_text = f"{risk_info.get('emoji', '')} {risk_info.get('level', 'N/A')} ({risk_info.get('score', 'N/A')})"
                
                geo_info = res.get('info', {})
                details = f"({geo_info.get('country', 'N/A')} - {geo_info.get('as', 'N/A')})"
                ip_info = f"{res.get('proxyIP')} {details}\n{risk_text}"
                message_parts.append(f"```{number_emoji}\n{ip_info}```")
            
            if i == len(successful_chunks) - 1:
                message_parts.append("\n**Test Completed.**")

            final_message_text = "\n".join(message_parts)
            await context.bot.send_message(chat_id=target_chat_id, text=final_message_text, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.5)

        # Sort final list by IP address for copy/file output
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
            
# --- Command & Conversation Handlers (No changes from here onwards) ---
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

    sent_message = await update.message.reply_text("Processing your input...")
    inputs = update.message.text.split()
    await process_command_logic(update, context, command, inputs, sent_message)
    return ConversationHandler.END

async def process_command_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str, inputs: list, message):
    chat_id, message_id = message.chat_id, message.message_id
    
    if command == "proxyip":
        await test_ips_and_update_message(context, chat_id, message_id, inputs, "Proxy IP Results")
    elif command == "iprange":
        ips_to_check, range_map, title = [], None, "IP Range Results"
        if len(inputs) > 1:
            range_map = {}
            for i, range_str in enumerate(inputs):
                range_map[i] = range_str
                for ip in parse_ip_range(range_str):
                    ips_to_check.append({"ip": ip, "range_index": i})
            title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in range_map.items()]
            title = "**Results for IP Ranges:**\n" + "\n".join(title_parts)
        else:
            ips_to_check = [ip for range_str in inputs for ip in parse_ip_range(range_str)]
        
        if not ips_to_check:
            await message.edit_text("Invalid range format or no IPs found in range(s).")
        else:
            await test_ips_and_update_message(context, chat_id, message_id, ips_to_check, title, range_map=range_map)
    elif command == "file":
        file_url = inputs[0]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', text)))
            if not ips_to_check: await message.edit_text("No valid IPs found in the file.")
            else: await test_ips_and_update_message(context, chat_id, message.message_id, ips_to_check, "File Test Results")
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
    for domain in inputs:
        if 'http://' in domain or 'https://' in domain or '/' in domain:
            await update.message.reply_text(
                "Invalid format. Please provide the domain without any protocol or slashes.\n\n"
                "Example: nima.nscl.ir\n"
                "Please send the correct domain, or /cancel to quit."
            )
            return AWAIT_DOMAIN_INPUT 

        if not re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$', domain):
            await update.message.reply_text(
                f"The domain format for '{domain}' is incorrect.\n\n"
                "Example: nima.nscl.ir\n"
                "Please send the correct domain, or /cancel to quit."
            )
            return AWAIT_DOMAIN_INPUT

    sent_message = await update.message.reply_text(f"Resolving {len(inputs)} domain(s)...")
    ips_to_check, domain_map, title = [], None, ""
    
    if len(inputs) > 1:
        domain_map = {}
        for i, domain_item in enumerate(inputs):
             api_result = await fetch_from_api("resolve", {"domain": domain_item})
             if api_result.get("success"):
                 domain_map[i] = domain_item
                 for ip in api_result.get("ips", []): ips_to_check.append({"ip": ip, "domain_index": i})
        title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in domain_map.items()]
        title = "**Results for Domains:**\n" + "\n".join(title_parts)
    else:
        domain_item = inputs[0]
        api_result = await fetch_from_api("resolve", {"domain": domain_item})
        if api_result.get("success"):
            ips_to_check.extend(api_result.get("ips", []))
        title = f"**Results for:** `{inputs[0]}`"

    unique_ips_to_check = list({(item['ip'] if isinstance(item, dict) else item): item for item in ips_to_check}.values())
    if not unique_ips_to_check:
        await sent_message.edit_text("Could not resolve any IPs from the provided domains.")
    else:
        await test_ips_and_update_message(context, sent_message.chat_id, sent_message.message_id, unique_ips_to_check, title, domain_map=domain_map)
    
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
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="freeproxy_cancel")])
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
    chat_id_str, chat_type = update.message.text, context.user_data.get('add_chat_type')
    context.user_data['new_chat_id'] = chat_id_str
    keyboard = [[InlineKeyboardButton("✅ Yes", callback_data="addconfirm_yes"), InlineKeyboardButton("❌ No", callback_data="addconfirm_no")]]
    if chat_type == 'group':
        prompt = f"You entered group ID: `{chat_id_str}`\n\nHas this bot been added to the group?"
    else:
        prompt = f"You entered channel: `{chat_id_str}`\n\nHave you made this bot an admin with 'Post Messages' permission?"
    await update.message.reply_text(prompt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return AWAIT_ADD_CONFIRMATION

async def addchat_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice, chat_type = query.data.split('_')[-1], context.user_data.get('add_chat_type')

    if choice == 'yes':
        await query.edit_message_text("Great! Now please send a custom name for this destination (e.g., 'My Tech Channel').")
        return AWAIT_CHAT_NAME
    else:
        if chat_type == 'channel': await query.edit_message_text("Action required: Please make me an admin in the channel with 'Post Messages' permission and try again using /addchat.")
        else: await query.edit_message_text("Action required: Please add me to the group and try again using /addchat.")
        context.user_data.clear()
        return ConversationHandler.END

async def addchat_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_str, name = str(update.message.from_user.id), update.message.text
    chat_id = context.user_data.pop('new_chat_id', None)
    if not chat_id: return ConversationHandler.END
    
    db = load_db()
    user_chats = db.get(user_id_str, [])
    try: final_chat_id = int(chat_id) if str(chat_id).startswith('-') else chat_id
    except ValueError: final_chat_id = chat_id
        
    if not any(str(c['chat_id']) == str(final_chat_id) for c in user_chats):
        user_chats.append({"chat_id": final_chat_id, "name": name})
        db[user_id_str] = user_chats
        save_db(db)
        await update.message.reply_text(f"✅ Destination '{name}' added successfully!")
    else:
        await update.message.reply_text("This chat ID is already registered.")
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
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="del_cancel")])
    await update.message.reply_text("Select a destination to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_CHAT_TO_DELETE

async def deletechat_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "del_cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    context.user_data['chat_to_delete'] = query.data.split('_')[-1]
    keyboard = [[InlineKeyboardButton("✅ Yes, delete it", callback_data="del_confirm_yes"), InlineKeyboardButton("❌ No, go back", callback_data="del_confirm_no")]]
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
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="del_cancel")])
        await query.edit_message_text("Select a destination to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_CHAT_TO_DELETE

    chat_id_to_delete = context.user_data.pop('chat_to_delete', None)
    user_chats = db.get(user_id_str, [])
    updated_chats = [chat for chat in user_chats if str(chat['chat_id']) != str(chat_id_to_delete)]
    
    if len(updated_chats) < len(user_chats):
        db[user_id_str] = updated_chats
        save_db(db)
        await query.edit_message_text("✅ Destination successfully deleted.")
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
        [InlineKeyboardButton("✨ Free Proxies by Country", callback_data="post_cmd_freeproxyip")],
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
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="post_cmd_back")])
        await query.edit_message_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))
        return AWAIT_POST_COUNTRY
    else:
        await query.edit_message_text(f"Great! Now please send the input for the `{command}` command.", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_COMMAND_INPUT

async def post_handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_chat_id_str, command = context.user_data.get('target_chat_id'), context.user_data.get('post_command')
    if not target_chat_id_str: return ConversationHandler.END
    
    confirmation_message = await update.message.reply_text("✅ Request received. The test will run in the background. Final results will be posted shortly...")
    inputs = update.message.text.split()
    context.application.create_task(run_post_command_logic(context, target_chat_id_str, command, inputs, confirmation_message))
    context.user_data.clear()
    return ConversationHandler.END

async def post_handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "post_cmd_back":
        keyboard = [[InlineKeyboardButton("Proxy IP Test", callback_data="post_cmd_proxyip")], [InlineKeyboardButton("IP Range Test", callback_data="post_cmd_iprange")], [InlineKeyboardButton("Domain Test", callback_data="post_cmd_domain")], [InlineKeyboardButton("File URL Test", callback_data="post_cmd_file")], [InlineKeyboardButton("✨ Free Proxies by Country", callback_data="post_cmd_freeproxyip")]]
        await query.edit_message_text("Now, select the type of test:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_COMMAND

    target_chat_id_str, country_code = context.user_data.get('target_chat_id'), query.data.split('_')[-1]
    if not target_chat_id_str: return ConversationHandler.END

    country_name_full = COUNTRIES.get(country_code, "Selected Country")
    confirmation_message = await query.edit_message_text(f"✅ Request received for {country_name_full}. The results will be posted shortly.")
    context.application.create_task(run_post_command_logic(context, target_chat_id_str, "freeproxyip", [country_code], confirmation_message, title_prefix=f"**{country_name_full} Test Results**"))
    context.user_data.clear()
    return ConversationHandler.END

async def run_post_command_logic(context: ContextTypes.DEFAULT_TYPE, target_chat_id_str: str, command: str, inputs: list, confirmation_message, title_prefix: str = ""):
    ips_to_check, domain_map, range_map, title = [], None, None, title_prefix
    try: target_chat_id = int(target_chat_id_str) if target_chat_id_str.startswith('-') else target_chat_id_str
    except ValueError: target_chat_id = target_chat_id_str

    try:
        if command == "proxyip":
            ips_to_check, title = inputs, title or "Proxy IP Test Results:"
        elif command == "iprange":
            if len(inputs) > 1:
                range_map = {i: r for i, r in enumerate(inputs)}
                for i, r in enumerate(inputs):
                    for ip in parse_ip_range(r): ips_to_check.append({"ip": ip, "range_index": i})
                title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in range_map.items()]
                title = "**Results for IP Ranges:**\n" + "\n".join(title_parts)
            else:
                ips_to_check = [ip for r in inputs for ip in parse_ip_range(r)]
                title = title or "IP Range Test Results:"
        elif command == "domain":
            valid_inputs = []
            for domain_input in inputs:
                clean_domain = re.sub(r'^(https?://)?(www\.)?', '', domain_input).split('/')[0]
                if re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$', clean_domain):
                    valid_inputs.append(clean_domain)
            if not valid_inputs:
                await context.bot.send_message(chat_id=confirmation_message.chat_id, text="Invalid domain format provided. Operation cancelled.")
                await context.bot.delete_message(chat_id=confirmation_message.chat_id, message_id=confirmation_message.message_id)
                return
            
            if len(valid_inputs) > 1:
                domain_map = {}
                for i, domain in enumerate(valid_inputs):
                    api_result = await fetch_from_api("resolve", {"domain": domain})
                    if api_result.get("success"):
                        domain_map[i] = domain
                        for ip in api_result.get("ips", []): ips_to_check.append({"ip": ip, "domain_index": i})
                title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in domain_map.items()]
                title = "**Results for Domains:**\n" + "\n".join(title_parts)
            else:
                domain = valid_inputs[0]
                api_result = await fetch_from_api("resolve", {"domain": domain})
                if api_result.get("success"): ips_to_check.extend(api_result.get("ips", []))
                title = title or f"**Results for:** `{domain}`"
            ips_to_check = list({(item['ip'] if isinstance(item, dict) else item): item for item in ips_to_check}.values())
        elif command == "file":
            async with httpx.AsyncClient() as client:
                response = await client.get(inputs[0], timeout=15)
                response.raise_for_status()
                ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', response.text)))
            title = title or "File Test Results:"
        elif command == "freeproxyip":
            country_code = inputs[0]
            url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                response.raise_for_status()
                ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', response.text)))
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
    await query.answer()
    parts = query.data.split('_', 1)
    callback_type, data = parts[0], (parts[1] if len(parts) > 1 else None)

    if callback_type == "freeproxy" and data == "cancel":
        await query.edit_message_text("Operation cancelled.")
        return

    if callback_type == "country":
        country_code = data
        country_name_full = COUNTRIES.get(country_code, "Selected Country")
        url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
        sent_message = await query.edit_message_text(text=f"Fetching IPs for {country_name_full}...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', text)))
            if not ips_to_check: await sent_message.edit_text(f"No IPs found for {country_name_full}.")
            else: await test_ips_and_update_message(context, query.message.chat_id, sent_message.message_id, ips_to_check, f"**{country_name_full} Test Results**")
        except Exception as e: await sent_message.edit_text(f"Error getting proxies for {country_name_full}: {e}")
        return

    test_id = data
    if not test_id or test_id not in context.user_data:
        await query.answer("This test has expired or is invalid.", show_alert=True)
        try: await query.edit_message_reply_markup(reply_markup=None)
        except BadRequest: pass
        return

    if callback_type == 'pause':
        context.user_data[test_id]['status'] = 'paused'
        keyboard = [[InlineKeyboardButton("▶️ Resume", callback_data=f"resume_{test_id}"), InlineKeyboardButton("⏹️ Cancel", callback_data=f"cancel_{test_id}")]]
        context.user_data[test_id]['markup'] = InlineKeyboardMarkup(keyboard)
        try:
            current_text = query.message.text_markdown_v2.split("\n\n**Operation paused")[0]
            await query.edit_message_text(text=current_text + "\n\n**Operation paused. Click Resume to continue.**", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
             await query.edit_message_text(text=query.message.text + "\n\n**Operation paused. Click Resume to continue.**", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    elif callback_type == 'resume':
        context.user_data[test_id]['status'] = 'running'
        keyboard = [[InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{test_id}"), InlineKeyboardButton("⏹️ Cancel", callback_data=f"cancel_{test_id}")]]
        context.user_data[test_id]['markup'] = InlineKeyboardMarkup(keyboard)
        try:
            original_text = query.message.text.split("\n\n**Operation paused.")[0]
            await query.edit_message_text(text=original_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest: pass
    elif callback_type == 'cancel':
        context.user_data[test_id]['status'] = 'stopped'
        try: await query.edit_message_reply_markup(reply_markup=None)
        except BadRequest: pass

# --- Main Application Setup ---
async def post_init(application: Application):
    commands = [
        BotCommand("start", "👋 Start Using Bot"),
        BotCommand("proxyip", "Check Proxy IPs"),
        BotCommand("iprange", "Check Proxy IP Ranges"),
        BotCommand("domain", "Resolving Domains"),
        BotCommand("file", "Check Proxy IPs From a File URL"),
        BotCommand("freeproxyip", "✨ Get Free Proxies By Country"),
        BotCommand("addchat", "➕ Register a Channel/Group"),
        BotCommand("deletechat", "🗑️ Delete a Registered Channel/Group"),
        BotCommand("post", "🚀 Post Results To a Chat"),
        BotCommand("cancel", "❌ Cancel Current Operation"),
    ]
    await application.bot.set_my_commands(commands)
    
def main() -> None:
    cprint("made with ❤️‍🔥 by @mehdiasmart", "light_cyan")
    
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
            AWAIT_ADD_CONFIRMATION: [CallbackQueryHandler(addchat_confirmation, pattern="^addconfirm_")],
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
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("cancel", cancel_conversation))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
