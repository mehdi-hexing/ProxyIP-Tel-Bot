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

# Conversation states
AWAIT_MAIN_INPUT = 0
SELECT_ADD_TYPE, AWAIT_CHAT_ID, AWAIT_ADD_CONFIRMATION, AWAIT_CHAT_NAME = range(1, 5)
SELECT_TARGET_CHAT, SELECT_COMMAND, AWAIT_COMMAND_INPUT, AWAIT_POST_COUNTRY = range(5, 9)
SELECT_CHAT_TO_DELETE, CONFIRM_DELETION = range(9, 11)

COUNTRIES = {
    'ALL': '🌐 All Countries', 'AE': '🇦🇪 UAE', 'AL': '🇦🇱 Albania', 'AM': '🇦🇲 Armenia', 'AR': '🇦🇷 Argentina', 'AT': '🇦🇹 Austria', 'AU': '🇦🇺 Australia', 'AZ': '🇦🇿 Azerbaijan', 'BE': '🇧🇪 Belgium', 'BG': '🇧🇬 Bulgaria', 'BR': '🇧🇷 Brazil', 'CA': '🇨🇦 Canada', 'CH': '🇨🇭 Switzerland', 'CN': '🇨🇳 China', 'CO': '🇨🇴 Colombia', 'CY': '🇨🇾 Cyprus', 'CZ': '🇨🇿 Czechia', 'DE': '🇩🇪 Germany', 'DK': '🇩🇰 Denmark', 'EE': '🇪🇪 Estonia', 'ES': '🇪🇸 Spain', 'FI': '🇫🇮 Finland', 'FR': '🇫🇷 France', 'GB': '🇬🇧 UK', 'GI': '🇬🇮 Gibraltar', 'HK': '🇭🇰 Hong Kong', 'HU': '🇭🇺 Hungary', 'ID': '🇮🇩 Indonesia', 'IE': '🇮🇪 Ireland', 'IL': '🇮🇱 Israel', 'IN': '🇮🇳 India', 'IR': '🇮🇷 Iran', 'IT': '🇮🇹 Italy', 'JP': '🇯🇵 Japan', 'KR': '🇰🇷 South Korea', 'KZ': '🇰🇿 Kazakhstan', 'LT': '🇱🇹 Lithuania', 'LU': '🇱🇺 Luxembourg', 'LV': '🇱🇻 Latvia', 'MD': '🇲🇩 Moldova', 'MX': '🇲🇽 Mexico', 'MY': '🇲🇾 Malaysia', 'NL': '🇳🇱 Netherlands', 'NZ': '🇳🇿 New Zealand', 'PH': '🇵🇭 Philippines', 'PL': '🇵🇱 Poland', 'PR': '🇵🇷 Puerto Rico', 'PT': '🇵🇹 Portugal', 'QA': '🇶🇦 Qatar', 'RO': '🇷🇴 Romania', 'RS': '🇷🇸 Serbia', 'RU': '🇷🇺 Russia', 'SA': '🇸🇦 Saudi Arabia', 'SC': '🇸🇨 Seychelles', 'SE': '🇸🇪 Sweden', 'SG': '🇸🇬 Singapore', 'SK': '🇸🇰 Slovakia', 'TH': '🇹🇭 Thailand', 'TR': '🇹🇷 Turkey', 'TW': '🇹🇼 Taiwan', 'UA': '🇺🇦 Ukraine', 'US': '🇺🇸 USA', 'UZ': '🇺🇿 Uzbekistan', 'VN': '🇻🇳 Vietnam'
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
        if '/' in range_str and range_str.endswith('/24'):
            net = ipaddress.ip_network(range_str, strict=False)
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

# --- Live Testing Logic ---
async def test_ips_and_update_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, ips_to_check: list, title: str, domain_map: dict = None):
    test_id = str(uuid.uuid4())
    context.user_data[test_id] = {'status': 'running', 'ips': ips_to_check, 'checked_ips': set(), 'successful': [], 'domain_map': domain_map or {}}
    
    keyboard = [[
        InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{test_id}"),
        InlineKeyboardButton("⏹️ Cancel", callback_data=f"cancel_{test_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data[test_id]['markup'] = reply_markup

    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"Starting test for {len(ips_to_check)} IPs...", reply_markup=reply_markup)
    except BadRequest:
        try:
            new_message = await context.bot.send_message(chat_id=chat_id, text=f"Starting test for {len(ips_to_check)} IPs...", reply_markup=reply_markup)
            message_id = new_message.message_id
        except Exception as e:
            logger.error(f"Failed to send new message to {chat_id}: {e}")
            return
    
    context.application.create_task(process_ips_in_batches(context, chat_id, message_id, test_id, title))

async def process_ips_in_batches(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, test_id: str, title: str):
    try:
        test_data = context.user_data.get(test_id)
        if not test_data: return

        domain_map = test_data.get('domain_map', {})
        batch_size = 30
        last_update_text = ""
        
        while len(test_data['checked_ips']) < len(test_data['ips']):
            current_state = context.user_data.get(test_id, {}).get('status', 'stopped')
            if current_state == 'stopped': break
            if current_state == 'paused':
                await asyncio.sleep(1)
                continue

            unchecked_ip_objects = [ip_obj for ip_obj in test_data['ips'] if (ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj) not in test_data['checked_ips']]
            batch = unchecked_ip_objects[:batch_size]
            
            async def check_and_get_info(ip_obj):
                ip_to_check = ip_obj['ip'] if isinstance(ip_obj, dict) else ip_obj
                test_data['checked_ips'].add(ip_to_check)
                check_result = await fetch_from_api("check", {"proxyip": ip_to_check})
                if check_result and check_result.get("success"):
                    info_result = await fetch_from_api("ip-info", {"ip": check_result.get("proxyIP")})
                    result = {"ip": check_result.get("proxyIP"), "info": info_result}
                    if isinstance(ip_obj, dict): result['domain_index'] = ip_obj['domain_index']
                    return result
                return None

            results = await asyncio.gather(*(check_and_get_info(ip_obj) for ip_obj in batch))
            
            for res in results:
                if res: test_data['successful'].append(res)
            
            message_parts = [f"**{title}**", f"Checked: {len(test_data['checked_ips'])}/{len(test_data['ips'])} | Successful: {len(test_data['successful'])}", "---"]
            for res in test_data['successful']:
                details = f"({res['info'].get('country', 'N/A')} - {res['info'].get('as', 'N/A')})"
                prefix = ""
                if domain_map and 'domain_index' in res and res['domain_index'] in domain_map:
                    prefix = f"{format_number_with_emojis(res['domain_index'] + 1)} "
                message_parts.append(f"{prefix}`{res.get('ip')} {details}`")
            
            reply_text = "\n".join(message_parts)
            
            if reply_text != last_update_text:
                try:
                    current_markup = context.user_data.get(test_id, {}).get('markup')
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=reply_text, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup)
                    last_update_text = reply_text
                except BadRequest as e:
                    if "Message is not modified" not in str(e): logger.warning(f"Failed to edit message: {e}")
            await asyncio.sleep(1)

        final_status = test_data.get('status')
        successful_results = test_data.get('successful')

        final_message_text = "Operation stopped." if final_status == 'stopped' else f"**{title}**\nTest completed."
        if not successful_results:
            final_message_text = "Operation stopped." if final_status == 'stopped' else f"**{title}**\nNo successful proxies found."
            
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_message_text, parse_mode=ParseMode.MARKDOWN, reply_markup=None)

        if successful_results:
            sorted_ips = sorted([res['ip'] for res in successful_results], key=lambda ip: ipaddress.ip_address(ip.split(':')[0].replace('[','').replace(']','')))
            copy_text = "\n".join(sorted_ips)
            await context.bot.send_message(chat_id=chat_id, text=f"To copy all IPs, tap the code block below:\n```\n{copy_text}\n```", parse_mode=ParseMode.MARKDOWN_V2)

            file_name = f"successful_proxies_{uuid.uuid4().hex[:6]}"
            txt_file = io.BytesIO(copy_text.encode('utf-8'))
            await context.bot.send_document(chat_id=chat_id, document=txt_file, filename=f"{file_name}.txt")
            csv_file = io.BytesIO(copy_text.encode('utf-8'))
            await context.bot.send_document(chat_id=chat_id, document=csv_file, filename=f"{file_name}.csv")
            
    finally:
        if test_id in context.user_data: del context.user_data[test_id]

# --- Background Task Logic (for /post) ---
async def run_test_and_post(context: ContextTypes.DEFAULT_TYPE, target_chat_id, ips_to_check: list, title: str, confirmation_message):
    """Runs a test in the background and posts the final result to the target chat."""
    status_message = None
    try:
        status_message = await context.bot.send_message(chat_id=target_chat_id, text=f"Processing request for `{title}`...", parse_mode=ParseMode.MARKDOWN)
        
        successful_results = []
        batch_size = 30
        for i in range(0, len(ips_to_check), batch_size):
            batch = ips_to_check[i:i + batch_size]
            async def check_and_get_info(ip):
                check_result = await fetch_from_api("check", {"proxyip": ip})
                if check_result and check_result.get("success"):
                    return {"ip": check_result.get("proxyIP")}
                return None
            results = await asyncio.gather(*(check_and_get_info(ip) for ip in batch))
            for res in results:
                if res: successful_results.append(res)
            await asyncio.sleep(1)

        if not successful_results:
            await context.bot.edit_message_text(chat_id=target_chat_id, message_id=status_message.message_id, text=f"**{title}**\nNo successful proxies found.", parse_mode=ParseMode.MARKDOWN)
            return

        sorted_ips = sorted([res['ip'] for res in successful_results], key=lambda ip: ipaddress.ip_address(ip.split(':')[0].replace('[','').replace(']','')))
        copy_text = "\n".join(sorted_ips)
        
        final_text = f"**{title}**\n```\n{copy_text}\n```"
        await context.bot.send_message(chat_id=target_chat_id, text=final_text, parse_mode=ParseMode.MARKDOWN_V2)
        
        file_name = f"successful_proxies_{uuid.uuid4().hex[:6]}"
        txt_file = io.BytesIO(copy_text.encode('utf-8'))
        await context.bot.send_document(chat_id=target_chat_id, document=txt_file, filename=f"{file_name}.txt")
        csv_file = io.BytesIO(copy_text.encode('utf-8'))
        await context.bot.send_document(chat_id=target_chat_id, document=csv_file, filename=f"{file_name}.csv")

        if status_message: await context.bot.delete_message(chat_id=target_chat_id, message_id=status_message.message_id)

    except Exception as e:
        logger.error(f"Error in run_test_and_post: {e}")
        await context.bot.send_message(chat_id=confirmation_message.chat_id, text=f"An unexpected error occurred while posting: {e}")
    finally:
        try:
            await context.bot.delete_message(chat_id=confirmation_message.chat_id, message_id=confirmation_message.message_id)
        except Exception:
            pass

# --- Command & Conversation Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("👋 Welcome! Use the menu commands to start.")

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    
    message_to_send = "Operation cancelled."
    if update.message and '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        message_to_send = f"For future reference, please use `/cancel` without the mention.\n\nOperation cancelled."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message_to_send)
    else:
        await update.message.reply_text(message_to_send)
        
    return ConversationHandler.END
    
async def start_main_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    command_text = update.message.text.split()[0]
    command = command_text.replace('/', '').split('@')[0]
    
    if '@' in command_text and update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text(f"Please use the command without mentioning the bot's name, like `/{command}`.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    if update.message.chat.type != ChatType.PRIVATE:
        prompt_message = await update.message.reply_text(f"To use `/{command}`, please **reply** to this message with your input.", parse_mode=ParseMode.MARKDOWN)
        if 'pending_prompts' not in context.chat_data: context.chat_data['pending_prompts'] = {}
        context.chat_data[prompt_message.message_id] = {"command": command, "user_id": update.message.from_user.id}
        return AWAIT_MAIN_INPUT
    
    if context.args:
        sent_message = await update.message.reply_text(f"Processing your request...")
        await process_command_logic(update, context, command, context.args, sent_message)
        return ConversationHandler.END
    else:
        if context.user_data.get('active_prompt'):
            old_prompt = context.user_data.pop('active_prompt')
            try:
                await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=old_prompt['message_id'],
                    text=f"This `/{old_prompt['command']}` command has expired. Please proceed with the new command.",
                    parse_mode=ParseMode.MARKDOWN)
            except BadRequest: pass

        prompts = {'proxyip': "Please send your IP(s).", 'iprange': "Please send your IP range(s).", 'domain': "Please send your domain(s).", 'file': "Please send the file URL."}
        prompt_message = await update.message.reply_text(prompts.get(command, "Please send your input."))
        context.user_data['active_prompt'] = {'message_id': prompt_message.message_id, 'command': command}
        return AWAIT_MAIN_INPUT

async def handle_main_conversation_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    command = None
    if update.message.chat.type != ChatType.PRIVATE:
        if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
            prompt_message_id = update.message.reply_to_message.message_id
            pending_prompts = context.chat_data.get('pending_prompts', {})
            stored_data = pending_prompts.pop(str(prompt_message_id), None)
            if stored_data and stored_data["user_id"] == update.message.from_user.id:
                command = stored_data['command']
    else: # Private chat logic
        command = context.user_data.pop('active_prompt', {}).get('command')

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
        all_ips = [ip for range_str in inputs for ip in parse_ip_range(range_str)]
        if not all_ips: await message.edit_text("Invalid range format provided.")
        else: await test_ips_and_update_message(context, chat_id, message_id, all_ips, "IP Range Results")
    elif command == "domain":
        await message.edit_text(f"Resolving {len(inputs)} domain(s)...")
        ips_to_check, domain_map = [], {}
        for i, domain in enumerate(inputs):
             api_result = await fetch_from_api("resolve", {"domain": domain})
             if api_result.get("success"):
                 domain_map[i] = domain
                 for ip in api_result.get("ips", []): ips_to_check.append({"ip": ip, "domain_index": i})
        
        unique_ips_to_check = list({item['ip']: item for item in ips_to_check}.values())
        if not unique_ips_to_check:
            await message.edit_text("Could not resolve any IPs from the provided domains.")
        else:
            title_parts = [f"{format_number_with_emojis(i+1)} `{name}`" for i, name in domain_map.items()]
            title = "**Results for:**\n" + "\n".join(title_parts)
            await test_ips_and_update_message(context, chat_id, message_id, unique_ips_to_check, title, domain_map)
    elif command == "file":
        file_url = inputs[0]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))
            if not ips_to_check: await message.edit_text("No valid IPs found in the file.")
            else: await test_ips_and_update_message(context, chat_id, message.message_id, ips_to_check, "File Test Results")
        except Exception as e: await message.edit_text(f"Error processing file: {e}")

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
    chat_id_str = update.message.text
    chat_type = context.user_data.get('add_chat_type')
    
    context.user_data['new_chat_id'] = chat_id_str
    
    keyboard = [[
        InlineKeyboardButton("✅ Yes", callback_data="addconfirm_yes"),
        InlineKeyboardButton("❌ No", callback_data="addconfirm_no")
    ]]
    if chat_type == 'group':
        prompt = f"You entered group ID: `{chat_id_str}`\n\nHas this bot been added to the group?"
    else:
        prompt = f"You entered channel: `{chat_id_str}`\n\nHave you made this bot an admin with 'Post Messages' permission?"
        
    await update.message.reply_text(prompt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return AWAIT_ADD_CONFIRMATION

async def addchat_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split('_')[-1]
    chat_type = context.user_data.get('add_chat_type')

    if choice == 'yes':
        await query.edit_message_text("Great! Now please send a custom name for this destination (e.g., 'My Tech Channel').")
        return AWAIT_CHAT_NAME
    else:
        if chat_type == 'channel':
            await query.edit_message_text("Action required: Please make me an admin in the channel with 'Post Messages' permission and try again using /addchat.")
        else:
            await query.edit_message_text("Action required: Please add me to the group and try again using /addchat.")
        context.user_data.clear()
        return ConversationHandler.END

async def addchat_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_str = str(update.message.from_user.id)
    chat_id = context.user_data.pop('new_chat_id', None)
    if not chat_id: return ConversationHandler.END
    
    name = update.message.text
    db = load_db()
    user_chats = db.get(user_id_str, [])
    
    try:
        final_chat_id = int(chat_id) if str(chat_id).startswith('-') else chat_id
    except ValueError:
        final_chat_id = chat_id
        
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

    user_id_str = str(update.message.from_user.id)
    db = load_db()
    user_chats = db.get(user_id_str, [])
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

    chat_id_to_delete = query.data.split('_')[-1]
    context.user_data['chat_to_delete'] = chat_id_to_delete
    
    keyboard = [[
        InlineKeyboardButton("✅ Yes, delete it", callback_data="del_confirm_yes"),
        InlineKeyboardButton("❌ No, go back", callback_data="del_confirm_no")
    ]]
    await query.edit_message_text(f"Are you sure you want to delete this destination?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_DELETION

async def deletechat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "del_confirm_no":
        user_id_str = str(query.from_user.id)
        db = load_db()
        user_chats = db.get(user_id_str, [])
        keyboard = [[InlineKeyboardButton(chat['name'], callback_data=f"del_chat_{chat['chat_id']}")] for chat in user_chats]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="del_cancel")])
        await query.edit_message_text("Select a destination to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_CHAT_TO_DELETE

    user_id_str = str(query.from_user.id)
    chat_id_to_delete = context.user_data.pop('chat_to_delete', None)
    
    db = load_db()
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
        
    db = load_db()
    user_chats = db.get(str(update.message.from_user.id), [])
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
        for code, name in COUNTRIES.items():
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
    target_chat_id_str = context.user_data.get('target_chat_id')
    command = context.user_data.get('post_command')
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
        return await post_select_chat(update, context)

    target_chat_id_str = context.user_data.get('target_chat_id')
    country_code = query.data.split('_')[-1]
    if not target_chat_id_str: return ConversationHandler.END

    country_name_full = COUNTRIES.get(country_code, "Selected Country")
    confirmation_message = await query.edit_message_text(f"✅ Request received for {country_name_full}. The results will be posted shortly.")
    
    context.application.create_task(run_post_command_logic(context, target_chat_id_str, "freeproxyip", [country_code], confirmation_message, title_prefix=f"{country_name_full} Test Results:"))
    
    context.user_data.clear()
    return ConversationHandler.END

async def run_post_command_logic(context: ContextTypes.DEFAULT_TYPE, target_chat_id_str: str, command: str, inputs: list, confirmation_message: Update.message, title_prefix: str = ""):
    """Gets IPs to check and calls the background tester for posting."""
    title = title_prefix or f"{command.replace('_', ' ').title()} Test Result:"
    ips_to_check = []
    
    try:
        target_chat_id = int(target_chat_id_str) if target_chat_id_str.startswith('-') else target_chat_id_str
    except ValueError:
        target_chat_id = target_chat_id_str

    try:
        if command == "proxyip": ips_to_check = inputs
        elif command == "iprange": ips_to_check = [ip for r in inputs for ip in parse_ip_range(r)]
        elif command == "domain":
            resolved_ips = []
            for domain in inputs:
                 api_result = await fetch_from_api("resolve", {"domain": domain})
                 if api_result.get("success"): resolved_ips.extend(api_result.get("ips", []))
            ips_to_check = list(set(resolved_ips))
        elif command == "file":
            async with httpx.AsyncClient() as client:
                response = await client.get(inputs[0], timeout=15)
                response.raise_for_status()
                ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', response.text)))
        elif command == "freeproxyip":
            url = COUNTRY_URLS.get(inputs[0]) or f"{COUNTRY_FILE_BASE_URL}{inputs[0].upper()}.txt"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15)
                response.raise_for_status()
                ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', response.text)))
                
        if not ips_to_check:
            await context.bot.send_message(chat_id=target_chat_id, text="No valid IPs found from your input to test.")
            return
            
        await run_test_and_post(context, target_chat_id, ips_to_check, title, confirmation_message)
    except Exception as e:
        await context.bot.send_message(chat_id=confirmation_message.chat_id, text=f"An error occurred during post operation: {e}")
        try: # Try to delete confirmation message even on failure
            await context.bot.delete_message(chat_id=confirmation_message.chat_id, message_id=confirmation_message.message_id)
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
            ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))
            if not ips_to_check: await sent_message.edit_text(f"No IPs found for {country_name_full}.")
            else: await test_ips_and_update_message(context, query.message.chat_id, sent_message.message_id, ips_to_check, f"[{country_name_full}] Test Result:")
        except Exception as e: await sent_message.edit_message_text(f"Error getting proxies for {country_name_full}: {e}")
        return

    test_id = data
    if not test_id or test_id not in context.user_data:
        await query.answer("This test has expired or is invalid.", show_alert=True)
        return

    if callback_type == 'pause':
        context.user_data[test_id]['status'] = 'paused'
        keyboard = [[InlineKeyboardButton("▶️ Resume", callback_data=f"resume_{test_id}"), InlineKeyboardButton("⏹️ Cancel", callback_data=f"cancel_{test_id}")]]
        context.user_data[test_id]['markup'] = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=query.message.text + "\n\n**Operation paused. Click Resume to continue.**", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    elif callback_type == 'resume':
        context.user_data[test_id]['status'] = 'running'
        keyboard = [[InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{test_id}"), InlineKeyboardButton("⏹️ Cancel", callback_data=f"cancel_{test_id}")]]
        context.user_data[test_id]['markup'] = InlineKeyboardMarkup(keyboard)
        original_text = query.message.text.split("\n\n**Operation paused.")[0]
        await query.edit_message_text(text=original_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    elif callback_type == 'cancel':
        context.user_data[test_id]['status'] = 'stopped'

async def post_init(application: Application):
    """Sets bot commands after initialization."""
    commands = [
        BotCommand("start", "🤖 Start Using Bot"),
        BotCommand("proxyip", "🔍 Check Proxy IPs"),
        BotCommand("iprange", "🔍 Check Proxy IP Ranges"),
        BotCommand("domain", "🔄 Resolving Domains"),
        BotCommand("file", "🔍 Check Proxy IPs From a File URL"),
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
    
    command_list = ["proxyip", "iprange", "domain", "file"]
    
    main_conv_handler = ConversationHandler(
        entry_points=[CommandHandler(cmd, start_main_conversation) for cmd in command_list],
        states={
            AWAIT_MAIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_conversation_input)],
        },
        fallbacks=[CommandHandler(cmd, start_main_conversation) for cmd in command_list] + 
                   [CommandHandler("start", start_command), 
                    CommandHandler("freeproxyip", freeproxyip_command),
                    CommandHandler("addchat", addchat_start),
                    CommandHandler("deletechat", deletechat_start),
                    CommandHandler("post", post_start),
                    CommandHandler("cancel", cancel_conversation)],
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
            AWAIT_POST_COUNTRY: [CallbackQueryHandler(post_handle_country_selection, pattern="^post_country_")]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("freeproxyip", freeproxyip_command))
    application.add_handler(main_conv_handler)
    application.add_handler(addchat_handler)
    application.add_handler(deletechat_handler)
    application.add_handler(post_handler)
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
