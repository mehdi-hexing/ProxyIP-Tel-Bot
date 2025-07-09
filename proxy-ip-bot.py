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
AWAIT_CHAT_ID_OR_FORWARD, AWAIT_CHAT_NAME = range(1, 3)
SELECT_TARGET_CHAT, SELECT_COMMAND, AWAIT_COMMAND_INPUT, AWAIT_POST_COUNTRY = range(3, 7)

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
                    prefix = f"{format_number_with_emojis(res['domain_index']+1)} "
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

# --- Command & Conversation Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("👋 Welcome! Use the menu commands to start.")

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END
    
async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles commands with/without args, starting a conversation if needed."""
    command = update.message.text.split()[0].replace('/', '')
    
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text(f"Please use the command without mentioning the bot's name, like `/{command}`.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    if context.args:
        sent_message = await update.message.reply_text(f"Processing your request...")
        await process_command_logic(update, context, command, context.args, sent_message)
        return ConversationHandler.END
    else:
        context.user_data['active_conversation'] = { "command": command }
        prompt_text = {
            'proxyip': "Please send your IP(s). In groups, please **reply** to this message.",
            'iprange': "Please send your IP range(s). In groups, please **reply** to this message.",
            'domain': "Please send your domain(s). In groups, please **reply** to this message.",
            'file': "Please send the file URL. In groups, please **reply** to this message."
        }.get(command, "Please send your input.")
        
        prompt_message = await update.message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN)
        context.user_data['active_conversation']['prompt_message_id'] = prompt_message.message_id
        return AWAIT_MAIN_INPUT

async def handle_conversation_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles user's text input after a command prompt."""
    active_conv = context.user_data.get('active_conversation')
    if not active_conv: return ConversationHandler.END
    
    command = active_conv.get('command')
    prompt_message_id = active_conv.get('prompt_message_id')
    
    if update.message.chat.type != ChatType.PRIVATE:
        if not update.message.reply_to_message or update.message.reply_to_message.message_id != prompt_message_id:
            return AWAIT_MAIN_INPUT # Not a reply to our prompt, keep waiting
            
    context.user_data.pop('active_conversation', None)
    sent_message = await update.message.reply_text("Processing your replied input...")
    inputs = update.message.text.split()
    await process_command_logic(update, context, command, inputs, sent_message)
    
    return ConversationHandler.END

async def process_command_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str, inputs: list, message):
    if command == "proxyip":
        await test_ips_and_update_message(context, message.chat_id, message.message_id, inputs, "Proxy IP Results")
    elif command == "iprange":
        all_ips = [ip for range_str in inputs for ip in parse_ip_range(range_str)]
        if not all_ips: await message.edit_text("Invalid range format provided.")
        else: await test_ips_and_update_message(context, message.chat_id, message.message_id, all_ips, "IP Range Results")
    elif command == "domain":
        await message.edit_text(f"Resolving {len(inputs)} domain(s)...")
        ips_to_check = []
        domain_map = {}
        title_parts = [f"{format_number_with_emojis(i+1)} `{domain}`" for i, domain in enumerate(inputs)]
        title = "**Results for:**\n" + "\n".join(title_parts)

        for i, domain in enumerate(inputs):
            api_result = await fetch_from_api("resolve", {"domain": domain})
            if api_result.get("success"):
                ips = api_result.get("ips", [])
                for ip in ips:
                    ips_to_check.append({"ip": ip, "domain_index": i})
                    domain_map[ip] = i # Map IP to its domain index for later
        
        unique_ips_to_check = list({item['ip']: item for item in ips_to_check}.values())
        if not unique_ips_to_check:
            await message.edit_text("Could not resolve any IPs from the provided domains.")
        else:
            await test_ips_and_update_message(context, message.chat_id, message.message_id, unique_ips_to_check, title, domain_map)
    elif command == "file":
        file_url = inputs[0]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))
            if not ips_to_check: await message.edit_text("No valid IPs found in the file.")
            else: await test_ips_and_update_message(context, message.chat_id, message.message_id, ips_to_check, "File Test Results")
        except Exception as e: await message.edit_text(f"Error processing file: {e}")

# --- Special Commands ---
async def freeproxyip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text(f"Please use `/freeproxyip` without mentioning the bot's name.", parse_mode=ParseMode.MARKDOWN)
        return
    keyboard = []
    row = []
    for code, name in COUNTRIES.items():
        row.append(InlineKeyboardButton(name, callback_data=f"country_{code}"))
        if len(row) == 2: keyboard.append(row); row = []
    if row: keyboard.append(row)
    await update.message.reply_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- /addchat Conversation ---
async def addchat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please send the Chat ID, or forward a message from the target channel/group.")
    return AWAIT_CHAT_ID_OR_FORWARD

async def addchat_receive_id_or_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.forward_from_chat:
        context.user_data['new_chat_id'] = update.message.forward_from_chat.id
        default_name = update.message.forward_from_chat.title
        context.user_data['new_chat_name_default'] = default_name
        await update.message.reply_text(f"Detected chat: '{default_name}'.\nPlease send a custom name for it, or send `ok` to use this name.", parse_mode=ParseMode.MARKDOWN)
    else:
        try:
            context.user_data['new_chat_id'] = int(update.message.text)
            await update.message.reply_text("Great! Now please send a custom name for this chat (e.g., 'My Tech Channel').")
        except (ValueError, TypeError):
            await update.message.reply_text("That doesn't look like a valid ID. Please send a number or forward a message.")
            return AWAIT_CHAT_ID_OR_FORWARD
    return AWAIT_CHAT_NAME

async def addchat_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id_str = str(update.message.from_user.id)
    chat_id = context.user_data.pop('new_chat_id', None)
    if not chat_id: return ConversationHandler.END
    
    name = update.message.text
    if name.lower() == 'ok':
        name = context.user_data.get('new_chat_name_default', 'Untitled Chat')

    db = load_db()
    if user_id_str not in db: db[user_id_str] = []
    if not any(c['chat_id'] == chat_id for c in db[user_id_str]):
        db[user_id_str].append({"chat_id": chat_id, "name": name})
        save_db(db)
        await update.message.reply_text(f"✅ Chat '{name}' added successfully!")
    else:
        await update.message.reply_text("This chat ID is already registered.")
    context.user_data.clear()
    return ConversationHandler.END

# --- /post Conversation ---
async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = load_db()
    user_chats = db.get(str(update.message.from_user.id), [])
    if not user_chats:
        await update.message.reply_text("You haven't added any chats yet. Use /addchat to add one first.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(chat['name'], callback_data=f"post_chat_{chat['chat_id']}")] for chat in user_chats]
    
    post_help_text = "Please select a channel or group to post in.\n\n*Note: To post content from the bot, you must make the bot an admin in the target channel and give it permission to post messages.*"
    await update.message.reply_text(post_help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return SELECT_TARGET_CHAT

async def post_select_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['target_chat_id'] = int(query.data.split('_')[-1])
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
        keyboard = [[InlineKeyboardButton(name, callback_data=f"post_country_{code}")] for code, name in COUNTRIES.items()]
        await query.edit_message_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))
        return AWAIT_POST_COUNTRY
    else:
        await query.edit_message_text(f"Great! Now please send the input for the `{command}` command.", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_COMMAND_INPUT

async def post_handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_chat_id = context.user_data.get('target_chat_id')
    command = context.user_data.get('post_command')
    if not target_chat_id or not command:
        await update.message.reply_text("Session expired. Please start over with /post.")
        return ConversationHandler.END
    await update.message.reply_text("✅ Request received. Posting results to the selected chat...")
    inputs = update.message.text.split()
    try:
        sent_message = await context.bot.send_message(chat_id=target_chat_id, text="Processing request...")
        await process_command_logic(context, update, command, inputs, sent_message)
    except Exception as e:
        logger.error(f"Failed to post to chat {target_chat_id}: {e}")
        await update.message.reply_text(f"❌ Could not post. Error: {e}")
    context.user_data.clear()
    return ConversationHandler.END

async def post_handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target_chat_id = context.user_data.get('target_chat_id')
    country_code = query.data.split('_')[-1]

    if not target_chat_id:
        await query.edit_message_text("Session expired. Please start over with /post.")
        return ConversationHandler.END

    country_name_full = COUNTRIES.get(country_code, "Selected Country")
    url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
    await query.edit_message_text(f"✅ Request received. Posting results for {country_name_full} to the selected chat...")
    
    try:
        sent_message = await context.bot.send_message(chat_id=target_chat_id, text=f"Fetching IPs for {country_name_full}...")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15)
            response.raise_for_status()
            text = response.text
        ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))
        if not ips_to_check:
            await sent_message.edit_text(f"No IPs found for {country_name_full}.")
        else:
            await test_ips_and_update_message(context, target_chat_id, sent_message.message_id, ips_to_check, f"[{country_name_full}] Test Result:")
    except Exception as e:
        await sent_message.edit_text(f"Error getting proxies for {country_name_full}: {e}")
    context.user_data.clear()
    return ConversationHandler.END


# --- Main Application Setup ---
async def post_init(application: Application):
    """Sets bot commands after initialization."""
    commands = [
        BotCommand("start", "🤖 Start Using Bot"),
        BotCommand("proxyip", "🔍 Check Proxy IPs"),
        BotCommand("iprange", "🔍 Check Proxy IP Ranges"),
        BotCommand("domain", "🔄 Resolving Domains"),
        BotCommand("file", "🔍 Check Proxy IPs from a file URL"),
        BotCommand("freeproxyip", "✨ Get Free Proxies By Country"),
        BotCommand("addchat", "➕ Register a Channel Or Group"),
        BotCommand("post", "🚀 Post Results To a Chat"),
        BotCommand("cancel", "❌ Cancel Current Operation"),
    ]
    await application.bot.set_my_commands(commands)
    
def main() -> None:
    cprint("made with ❤❤️‍🔥 by @mehdiasmart", "light_cyan")
    
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    command_list = ["proxyip", "iprange", "domain", "file"]
    
    main_conv_handler = ConversationHandler(
        entry_points=[CommandHandler(cmd, start_conversation) for cmd in command_list],
        states={
            AWAIT_MAIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_conversation_input)],
        },
        fallbacks=[CommandHandler(cmd, start_conversation) for cmd in command_list] + 
                   [CommandHandler("start", start_command), 
                    CommandHandler("freeproxyip", freeproxyip_command),
                    CommandHandler("addchat", addchat_start),
                    CommandHandler("post", post_start),
                    CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True
    )
    
    addchat_handler = ConversationHandler(
        entry_points=[CommandHandler("addchat", addchat_start)],
        states={
            AWAIT_CHAT_ID_OR_FORWARD: [MessageHandler(filters.TEXT | filters.FORWARDED & ~filters.COMMAND, addchat_receive_id)],
            AWAIT_CHAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addchat_receive_name)],
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
        per_message=True # To avoid issues with old keyboards
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("freeproxyip", freeproxyip_command))
    application.add_handler(main_conv_handler)
    application.add_handler(addchat_handler)
    application.add_handler(post_handler)
    
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
