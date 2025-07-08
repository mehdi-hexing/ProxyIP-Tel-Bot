import os
import logging
import uuid
import asyncio
import httpx
import io
import re
import ipaddress
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReplyKeyboardRemove
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
WORKER_URL = "https://YourProxyIPCheckerLink.pages.dev"
INPUT_STATE = 0

COUNTRIES = {
    'ALL': '🌐 All Countries', 'AE': '🇦🇪 UAE', 'AL': '🇦🇱 Albania', 'AM': '🇦🇲 Armenia', 'AR': '🇦🇷 Argentina', 'AT': '🇦🇹 Austria', 'AU': '🇦🇺 Australia', 'AZ': '🇦🇿 Azerbaijan', 'BE': '🇧🇪 Belgium', 'BG': '🇧🇬 Bulgaria', 'BR': '🇧🇷 Brazil', 'CA': '🇨🇦 Canada', 'CH': '🇨🇭 Switzerland', 'CN': '🇨🇳 China', 'CO': '🇨🇴 Colombia', 'CY': '🇨🇾 Cyprus', 'CZ': '🇨🇿 Czechia', 'DE': '🇩🇪 Germany', 'DK': '🇩🇰 Denmark', 'EE': '🇪🇪 Estonia', 'ES': '🇪🇸 Spain', 'FI': '🇫🇮 Finland', 'FR': '🇫🇷 France', 'GB': '🇬🇧 UK', 'GI': '🇬🇮 Gibraltar', 'HK': '🇭🇰 Hong Kong', 'HU': '🇭🇺 Hungary', 'ID': '🇮🇩 Indonesia', 'IE': '🇮🇪 Ireland', 'IL': '🇮🇱 Israel', 'IN': '🇮🇳 India', 'IR': '🇮🇷 Iran', 'IT': '🇮🇹 Italy', 'JP': '🇯🇵 Japan', 'KR': '🇰🇷 South Korea', 'KZ': '🇰🇿 Kazakhstan', 'LT': '🇱🇹 Lithuania', 'LU': '🇱🇺 Luxembourg', 'LV': '🇱🇻 Latvia', 'MD': '🇲🇩 Moldova', 'MX': '🇲🇽 Mexico', 'MY': '🇲🇾 Malaysia', 'NL': '🇳🇱 Netherlands', 'NZ': '🇳🇿 New Zealand', 'PH': '🇵🇭 Philippines', 'PL': '🇵🇱 Poland', 'PR': '🇵🇷 Puerto Rico', 'PT': '🇵🇹 Portugal', 'QA': '🇶🇦 Qatar', 'RO': '🇷🇴 Romania', 'RS': '🇷🇸 Serbia', 'RU': '🇷🇺 Russia', 'SA': '🇸🇦 Saudi Arabia', 'SC': '🇸🇨 Seychelles', 'SE': '🇸🇪 Sweden', 'SG': '🇸🇬 Singapore', 'SK': '🇸🇰 Slovakia', 'TH': '🇹🇭 Thailand', 'TR': '🇹🇷 Turkey', 'TW': '🇹🇼 Taiwan', 'UA': '🇺🇦 Ukraine', 'US': '🇺🇸 USA', 'UZ': '🇺🇿 Uzbekistan', 'VN': '🇻🇳 Vietnam'
}
COUNTRY_URLS = {"ALL": "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/02_proxies.csv"}
COUNTRY_FILE_BASE_URL = "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/"

# --- Helper Functions ---

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

# --- Live Testing Logic ---

async def test_ips_and_update_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, ips_to_check: list, title: str):
    test_id = str(uuid.uuid4())
    context.user_data[test_id] = {'status': 'running', 'ips': ips_to_check, 'checked_ips': set(), 'successful': []}
    
    keyboard = [[
        InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{test_id}"),
        InlineKeyboardButton("⏹️ Cancel", callback_data=f"cancel_{test_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data[test_id]['markup'] = reply_markup

    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"Starting test for {len(ips_to_check)} IPs...", reply_markup=reply_markup)
    
    context.application.create_task(process_ips_in_batches(context, chat_id, message_id, test_id, title))

async def process_ips_in_batches(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, test_id: str, title: str):
    try:
        test_data = context.user_data.get(test_id)
        if not test_data: return

        batch_size = 30
        last_update_text = ""
        
        while len(test_data['checked_ips']) < len(test_data['ips']):
            current_state = context.user_data.get(test_id, {}).get('status', 'stopped')
            if current_state == 'stopped':
                break
            if current_state == 'paused':
                await asyncio.sleep(1)
                continue

            unchecked_ips = [ip for ip in test_data['ips'] if ip not in test_data['checked_ips']]
            batch = unchecked_ips[:batch_size]
            
            async def check_and_get_info(ip):
                check_result = await fetch_from_api("check", {"proxyip": ip})
                test_data['checked_ips'].add(ip)
                if check_result and check_result.get("success"):
                    info_result = await fetch_from_api("ip-info", {"ip": check_result.get("proxyIP")})
                    return {"ip": check_result.get("proxyIP"), "info": info_result}
                return None

            results = await asyncio.gather(*(check_and_get_info(ip) for ip in batch))
            
            for res in results:
                if res: test_data['successful'].append(res)
            
            message_parts = [f"**{title}**", f"Checked: {len(test_data['checked_ips'])}/{len(test_data['ips'])} | Successful: {len(test_data['successful'])}", "---"]
            for res in test_data['successful']:
                details = f"({res['info'].get('country', 'N/A')} - {res['info'].get('as', 'N/A')})"
                message_parts.append(f"`{res.get('ip')} {details}`")
            
            reply_text = "\n\n".join(message_parts)
            
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

        final_message_text = ""
        if final_status == 'stopped':
            final_message_text = "Operation stopped."
        elif not successful_results:
            final_message_text = f"**{title}**\nNo successful proxies found."
        else:
            final_message_text = f"**{title}**\nTest completed."

        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_message_text, parse_mode=ParseMode.MARKDOWN, reply_markup=None)

        if successful_results:
            sorted_ips = sorted([res['ip'] for res in successful_results], key=ipaddress.ip_address)
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
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        return
    await update.message.reply_text("👋 Welcome! Use a command with arguments (e.g., `/proxyip 1.1.1.1`) or alone to get a prompt.")

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        return ConversationHandler.END

    command = update.message.text.split()[0].replace('/', '')
    
    if context.args:
        sent_message = await update.message.reply_text("Processing your request...")
        await process_command_logic(update, context, command, context.args, sent_message)
        return ConversationHandler.END
    else:
        context.user_data['command_type'] = command
        prompt_text = {
            'proxyip': "Please send your IP(s). In groups, please **reply** to this message.",
            'iprange': "Please send your IP range(s). In groups, please **reply** to this message.",
            'domain': "Please send your domain(s). In groups, please **reply** to this message.",
            'file': "Please send the file URL. In groups, please **reply** to this message."
        }.get(command, "Please send your input. In groups, please **reply** to this message.")
        
        prompt_message = await update.message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN)
        context.user_data['prompt_message_id'] = prompt_message.message_id
        return INPUT_STATE

async def handle_conversation_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    command = context.user_data.pop('command_type', None)
    prompt_message_id = context.user_data.pop('prompt_message_id', None)

    if update.message.chat.type != ChatType.PRIVATE:
        if not update.message.reply_to_message or update.message.reply_to_message.message_id != prompt_message_id:
            return ConversationHandler.END 
            
    if not command: return ConversationHandler.END

    sent_message = await update.message.reply_text("Processing your request...")
    inputs = update.message.text.split()
    await process_command_logic(update, context, command, inputs, sent_message)
    
    return ConversationHandler.END

async def process_command_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str, inputs: list, message):
    if command == "proxyip":
        await test_ips_and_update_message(context, update.message.chat_id, message.message_id, inputs, "Proxy IP Results")
    elif command == "iprange":
        all_ips = [ip for range_str in inputs for ip in parse_ip_range(range_str)]
        if not all_ips: await message.edit_text("Invalid range format provided.")
        else: await test_ips_and_update_message(context, update.message.chat_id, message.message_id, all_ips, "IP Range Results")
    elif command == "domain":
        await message.edit_text(f"Resolving {len(inputs)} domain(s)...")
        all_ips_to_check = []
        for domain in inputs:
             api_result = await fetch_from_api("resolve", {"domain": domain})
             if api_result.get("success"): all_ips_to_check.extend(api_result.get("ips", []))
        if not all_ips_to_check: await message.edit_text("Could not resolve any IPs from the provided domains.")
        else: await test_ips_and_update_message(context, update.message.chat_id, message.message_id, list(set(all_ips_to_check)), f"Results for {', '.join(inputs)}")
    elif command == "file":
        file_url = inputs[0]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url, timeout=15)
                response.raise_for_status()
                text = response.text
            ips_to_check = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))
            if not ips_to_check: await message.edit_text("No valid IPs found in the file.")
            else: await test_ips_and_update_message(context, update.message.chat_id, message.message_id, ips_to_check, "File Test Results")
        except Exception as e: await message.edit_text(f"Error processing file: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'command_type' in context.user_data: context.user_data.pop('command_type', None)
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
    
async def freeproxyip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if '@' in update.message.text.split()[0] and update.message.chat.type != ChatType.PRIVATE:
        return
    keyboard = []
    row = []
    for code, name in COUNTRIES.items():
        row.append(InlineKeyboardButton(name, callback_data=f"country_{code}"))
        if len(row) == 2: keyboard.append(row); row = []
    if row: keyboard.append(row)
    await update.message.reply_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Callback Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_', 1)
    callback_type = parts[0]
    data = parts[1] if len(parts) > 1 else None

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
        except Exception as e: await sent_message.edit_text(f"Error getting proxies for {country_name_full}: {e}")
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
    commands = [
        BotCommand("start", "👋 Start Using Bot"),
        BotCommand("proxyip", "Check Proxy IPs"),
        BotCommand("iprange", "Check IP Ranges"),
        BotCommand("domain", "Resolving Domain(s)"),
        BotCommand("file", "Check Proxy IPs From a File URL"),
        BotCommand("freeproxyip", "✨ Get Free Proxies By Country"),
        BotCommand("cancel", "❌ Cancel Current Operation"),
    ]
    await application.bot.set_my_commands(commands)

# --- Main Application Setup ---
def main() -> None:
    cprint("This Bot Made With ❤️ By @mehdiasmart", "light_cyan")
    
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("proxyip", start_conversation),
            CommandHandler("iprange", start_conversation),
            CommandHandler("domain", start_conversation),
            CommandHandler("file", start_conversation),
        ],
        states={
            INPUT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_conversation_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("freeproxyip", freeproxyip_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
