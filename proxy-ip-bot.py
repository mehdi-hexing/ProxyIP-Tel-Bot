import os
import logging
import uuid
import asyncio
import requests
import io
import re
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import BadRequest
from termcolor import cprint

# --- Initial settings ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Fixes ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WORKER_URL = "https://check79.pages.dev"
# States for ConversationHandler
INPUT_PROXYIP, INPUT_IPRANGE, INPUT_FILE, INPUT_DOMAIN = range(4)

COUNTRIES = {
    'ALL': '🌐 All Countries', 'AE': '🇦🇪 United Arab Emirates', 'AL': '🇦🇱 Albania', 'AM': '🇦🇲 Armenia', 
    'AR': '🇦🇷 Argentina', 'AT': '🇦🇹 Austria', 'AU': '🇦🇺 Australia', 'AZ': '🇦🇿 Azerbaijan', 
    'BE': '🇧🇪 Belgium', 'BG': '🇧🇬 Bulgaria', 'BR': '🇧🇷 Brazil', 'CA': '🇨🇦 Canada', 
    'CH': '🇨🇭 Switzerland', 'CN': '🇨🇳 China', 'CO': '🇨🇴 Colombia', 'CY': '🇨🇾 Cyprus', 
    'CZ': '🇨🇿 Czech Republic', 'DE': '🇩🇪 Germany', 'DK': '🇩🇰 Denmark', 'EE': '🇪🇪 Estonia', 
    'ES': '🇪🇸 Spain', 'FI': '🇫🇮 Finland', 'FR': '🇫🇷 France', 'GB': '🇬🇧 United Kingdom', 
    'GI': '🇬🇮 Gibraltar', 'HK': '🇭🇰 Hong Kong', 'HU': '🇭🇺 Hungary', 'ID': '🇮🇩 Indonesia', 
    'IE': '🇮🇪 Ireland', 'IL': '🇮🇱 Israel', 'IN': '🇮🇳 India', 'IR': '🇮🇷 Iran', 'IT': '🇮🇹 Italy', 
    'JP': '🇯🇵 Japan', 'KR': '🇰🇷 South Korea', 'KZ': '🇰🇿 Kazakhstan', 'LT': '🇱🇹 Lithuania', 
    'LU': '🇱🇺 Luxembourg', 'LV': '🇱🇻 Latvia', 'MD': '🇲🇩 Moldova', 'MX': '🇲🇽 Mexico', 
    'MY': '🇲🇾 Malaysia', 'NL': '🇳🇱 Netherlands', 'NZ': '🇳🇿 New Zealand', 'PH': '🇵🇭 Philippines', 
    'PL': '🇵🇱 Poland', 'PR': '🇵🇷 Puerto Rico', 'PT': '🇵🇹 Portugal', 'QA': '🇶🇦 Qatar', 
    'RO': '🇷🇴 Romania', 'RS': '🇷🇸 Serbia', 'RU': '🇷🇺 Russia', 'SA': '🇸🇦 Saudi Arabia', 
    'SC': '🇸🇨 Seychelles', 'SE': '🇸🇪 Sweden', 'SG': '🇸🇬 Singapore', 'SK': '🇸🇰 Slovakia', 
    'TH': '🇹🇭 Thailand', 'TR': '🇹🇷 Turkey', 'TW': '🇹🇼 Taiwan', 'UA': '🇺🇦 Ukraine', 
    'US': '🇺🇸 United States', 'UZ': '🇺🇿 Uzbekistan', 'VN': '🇻🇳 Vietnam'
}

COUNTRY_URLS = {
    "ALL": "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/02_proxies.csv",
}
COUNTRY_FILE_BASE_URL = "https://raw.githubusercontent.com/NiREvil/vless/main/sub/country_proxies/"

# --- Auxiliary functions ---

async def fetch_from_api(endpoint: str, params: dict = None) -> dict:
    """Helper function to fetch data from our worker's API."""
    try:
        response = requests.get(f"{WORKER_URL}/api/{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for {endpoint}: {e}")
        return {"success": False, "error": str(e)}

def format_number_with_emojis(n: int) -> str:
    """Converts a number to its emoji equivalent."""
    number_emojis = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
    return "".join(number_emojis[int(digit)] for digit in str(n))

def get_copy_all_button(context: ContextTypes.DEFAULT_TYPE, results: list) -> InlineKeyboardButton | None:
    """Creates a 'Copy All' button if there are enough results."""
    if len(results) > 1:
        ip_list_id = str(uuid.uuid4())
        context.user_data[ip_list_id] = results
        return InlineKeyboardButton("📋 Copy All Successful IPs", callback_data=f"copy_{ip_list_id}")
    return None
    
# --- Live Testing Logic ---

async def live_test_and_update(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, ips_to_check: list, title: str, send_files: bool = False):
    """Generic function for live testing and updating a message."""
    successful_results = []
    checked_count = 0
    total_ips = len(ips_to_check)
    
    async def process_batch(batch):
        nonlocal checked_count
        tasks = [fetch_from_api("check", {"proxyip": ip}) for ip in batch]
        results = await asyncio.gather(*tasks)
        
        newly_successful = []
        for res, ip_to_check in zip(results, batch):
            checked_count += 1
            if res and res.get("success"):
                ip_info = await fetch_from_api("ip-info", {"ip": res.get("proxyIP")})
                res_with_info = {"ip": res.get("proxyIP"), "info": ip_info}
                newly_successful.append(res_with_info)
        return newly_successful

    batch_size = 10
    last_update_text = ""
    for i in range(0, total_ips, batch_size):
        batch = ips_to_check[i:i + batch_size]
        new_results = await process_batch(batch)
        successful_results.extend(new_results)
        
        message_parts = [f"**{title}**", f"Checked: {checked_count}/{total_ips} | Successful: {len(successful_results)}", "---"]
        for res in successful_results:
            details = f"({res['info'].get('country', 'N/A')} - {res['info'].get('as', 'N/A')})"
            message_parts.append(f"`{res.get('ip')}` {details}")
        
        reply_text = "\n".join(message_parts)
        
        if reply_text != last_update_text:
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=reply_text, parse_mode=ParseMode.MARKDOWN)
                last_update_text = reply_text
            except BadRequest as e:
                if "Message is not modified" not in str(e): logger.warning(f"Failed to edit message: {e}")
        await asyncio.sleep(0.5)

    if successful_results:
        button = get_copy_all_button(context, [res['ip'] for res in successful_results])
        if button:
            await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=InlineKeyboardMarkup([[button]]))

        if send_files:
            file_content = "\n".join([res['ip'] for res in successful_results])
            file_name = f"proxies_{uuid.uuid4().hex[:6]}.txt"
            txt_file = io.BytesIO(file_content.encode('utf-8'))
            csv_file = io.BytesIO(file_content.encode('utf-8'))
            
            await context.bot.send_document(chat_id=chat_id, document=txt_file, filename=file_name, caption="TXT file of successful IPs.")
            await context.bot.send_document(chat_id=chat_id, document=csv_file, filename=file_name.replace('.txt', '.csv'), caption="CSV file of successful IPs.")


# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and sets up menu commands."""
    commands = [
        BotCommand("start", "👋 Show welcome message"),
        BotCommand("proxyip", "Check one or more Proxy IPs"),
        BotCommand("domain", "Resolve and check domain(s)"),
        BotCommand("file", "Check IPs from a file URL"),
        BotCommand("freeproxyip", "✨ Get free proxies by country"),
    ]
    await context.bot.set_my_commands(commands)
    await update.message.reply_text("👋 Welcome! Use the menu commands or send IPs/domains directly to get started.")

async def freeproxyip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a keyboard with country options."""
    keyboard = []
    row = []
    for code, name in COUNTRIES.items():
        row.append(InlineKeyboardButton(name, callback_data=f"startlive_{code}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    await update.message.reply_text("Select from the list of countries below:", reply_markup=InlineKeyboardMarkup(keyboard))

async def prompt_for_input(update: Update, prompt_message: str, next_state: int) -> int:
    await update.message.reply_text(prompt_message, parse_mode=ParseMode.MARKDOWN)
    return next_state
    
async def domain_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await prompt_for_input(update, "Enter domain(s). Separate multiple entries with a *new line*.", INPUT_DOMAIN)

async def file_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
     return await prompt_for_input(update, "Enter the URL of the .txt or .csv file.", INPUT_FILE)

# --- Response Handlers ---

async def handle_domain_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes user input for domains with live updates."""
    domains = update.message.text.split()
    sent_message = await update.message.reply_text(f"Resolving {len(domains)} domain(s)...")
    
    ips_to_check_with_domain = []
    domain_map = {}
    
    for i, domain in enumerate(domains):
        try:
            resolved_ips = await resolveDomain(domain)
            domain_map[i] = domain
            for ip in resolved_ips:
                ips_to_check_with_domain.append({"ip": ip, "domain_index": i})
        except Exception as e:
            await update.message.reply_text(f"Could not resolve {domain}: {e}")

    unique_ips = list({item['ip']: item for item in ips_to_check_with_domain}.values())
    await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_message.message_id, text=f"Checking {len(unique_ips)} resolved IPs...")

    # A more complex live update logic is needed here to show domain numbers
    # For now, this is a simplified version.
    successful_results = []
    for ip_obj in unique_ips:
        res = await fetch_from_api("check", {"proxyip": ip_obj['ip']})
        if res.get("success"):
            info = await fetch_from_api("ip-info", {"ip": res.get("proxyIP")})
            successful_results.append({**res, "info": info, "domain_index": ip_obj['domain_index']})

    title_parts = [f"{format_number_with_emojis(i+1)} {name}" for i, name in domain_map.items()]
    title = ", ".join(title_parts)
    
    message_parts = [f"**Results for: {title}**", "---"]
    for res in successful_results:
        details = f"({res['info'].get('country', 'N/A')} - {res['info'].get('as', 'N/A')})"
        prefix = format_number_with_emojis(res['domain_index']+1)
        message_parts.append(f"{prefix} `{res.get('proxyIP')}` {details}")

    button = get_copy_all_button(context, [res['proxyIP'] for res in successful_results])
    await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=sent_message.message_id, text="\n".join(message_parts), reply_markup=InlineKeyboardMarkup([[button]]) if button else None, parse_mode=ParseMode.MARKDOWN)

    return ConversationHandler.END

# ... Other handlers for proxyip, file etc. would be similarly structured ...

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


# --- Inline & Callback Handlers ---

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline queries for IPs and countries."""
    query = update.inline_query.query
    if not query: return

    results = []
    # Search for country name
    matched_countries = {code: name for code, name in COUNTRIES.items() if query.lower() in name.lower()}

    if matched_countries:
        for code, name in matched_countries.items():
            results.append(
                InlineQueryResultArticle(
                    id=f"country_{code}",
                    title=name,
                    description=f"Get proxies from {name.split(' ', 1)[-1]}",
                    input_message_content=InputTextMessageContent(f"Click the button to start the test for {name.split(' ', 1)[-1]}."),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(f"Start Test for {name.split(' ', 1)[-1]}", callback_data=f"startlive_{code}")
                    ]])
                )
            )
    else: # Fallback to IP check
        first_ip = query.split(',')[0].strip()
        if first_ip:
            check_result = await fetch_from_api("check", {"proxyip": first_ip})
            title = "✅ Valid IP" if check_result.get("success") else "❌ Invalid IP"
            description = f"Click for details of {check_result.get('proxyIP')}"
            message_text = f"`{check_result.get('proxyIP')}`" # Simplified
            results.append(
                InlineQueryResultArticle(id=str(uuid.uuid4()), title=title, description=description,
                    input_message_content=InputTextMessageContent(message_text, parse_mode=ParseMode.MARKDOWN))
            )
            
    await update.inline_query.answer(results, cache_time=10)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all button clicks."""
    query = update.callback_query
    await query.answer()
    
    callback_type, data = query.data.split('_', 1)
    
    if callback_type == "copy":
        if data in context.user_data:
            await query.answer(text="Copied successfully!", show_alert=True)
        else:
            await query.answer(text="Error: Data expired or not found.", show_alert=True)
            
    elif callback_type == "startlive":
        country_code = data
        country_name_full = COUNTRIES.get(country_code, "Selected Country")
        country_name = country_name_full.split(' ', 1)[-1]
        
        url = COUNTRY_URLS.get(country_code) or f"{COUNTRY_FILE_BASE_URL}{country_code.upper()}.txt"
        
        sent_message = await query.edit_message_text(text=f"Fetching IPs for {country_name} and starting tests...")

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            text = response.text
            
            forgiving_ipv4 = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ips_to_check = list(set(re.findall(forgiving_ipv4, text)))
            
            await live_test_and_update(
                context=context,
                chat_id=query.message.chat_id,
                message_id=sent_message.message_id,
                ips_to_check=ips_to_check,
                title=f"[{country_name_full}] Test Result:",
                send_files=(country_code == "ALL")
            )
        except Exception as e:
            await context.bot.edit_message_text(chat_id=query.message.chat_id, message_id=sent_message.message_id, text=f"Error getting proxies for {country_name}: {e}")

# --- Main ---
def main() -> None:
    cprint("made with ❤️ by @mehdiasmart", "light_cyan")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("domain", domain_start),
            CommandHandler("file", file_start),
            # Add other command handlers here if needed
        ],
        states={
            INPUT_DOMAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_domain_input)],
            INPUT_FILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_file_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("freeproxyip", freeproxyip_command))
    application.add_handler(conv_handler)
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
