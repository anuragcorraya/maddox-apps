import os
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Load environment variables from .env file for local testing
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fetch environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_REPO_URL = "https://raw.githubusercontent.com/NikhilKain/vyxel-apps/main/apps.json"

# Lightweight HTTP Health Check Server for Render Free Web Service
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Vyxel Telegram Bot is active and healthy!")

    def log_message(self, format, *args):
        # Silence HTTP request log spam in Render logs
        return

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Starting HTTP Health-Check server on port {port}...")
    server.serve_forever()

# Fallback dataset in case GitHub fetch fails or is temporarily unavailable
FALLBACK_APPS = {
    "mobile": [
        {
            "name": "Vyxel Store",
            "description": "An open-source, lightweight app store for Android to fetch and update apps directly from GitHub and F-Droid.",
            "screenshots": [
                "https://raw.githubusercontent.com/NikhilKain/vyxel-apps/main/fastlane/metadata/android/en-US/images/phoneScreenshots/1.png"
            ],
            "download_url": "https://github.com/NikhilKain/vyxel-apps/releases",
            "github_url": "https://github.com/NikhilKain/vyxel-apps"
        }
    ],
    "desktop": [
        {
            "name": "Vyxel Desktop Client (Upcoming)",
            "description": "Cross-platform desktop dashboard to manage open-source apps and repositories.",
            "screenshots": [],
            "download_url": "https://github.com/NikhilKain",
            "github_url": "https://github.com/NikhilKain"
        }
    ]
}

def fetch_apps_from_github():
    """Fetches application catalog JSON from GitHub repository."""
    try:
        response = requests.get(GITHUB_REPO_URL, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error fetching data from GitHub: {e}")
    return FALLBACK_APPS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command and renders the main interactive menu."""
    keyboard = [
        [
            InlineKeyboardButton("📱 Mobile Apps", callback_data="cat_mobile"),
            InlineKeyboardButton("💻 Desktop Apps", callback_data="cat_desktop"),
        ],
        [
            InlineKeyboardButton("🌐 All GitHub Projects", callback_data="cat_all"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "👋 **Welcome to Vyxel Apps Bot!**\n\n"
        "Explore curated open-source Android & Desktop apps directly from `NikhilKain/vyxel-apps`.\n\n"
        "Please select a category below to browse available applications:"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks and displays apps with screenshots and descriptions."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "main_menu":
        await start(update, context)
        return

    apps_data = fetch_apps_from_github()
    category_key = data.replace("cat_", "")
    
    selected_apps = []
    if category_key == "all":
        for cat in apps_data:
            selected_apps.extend(apps_data[cat])
    else:
        selected_apps = apps_data.get(category_key, [])
        
    if not selected_apps:
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
        await query.message.edit_text(
            "⚠️ No applications found in this category right now.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await query.message.edit_text(f"🔍 Fetching {len(selected_apps)} application(s)... Please wait.")

    for app in selected_apps:
        name = app.get("name", "Unknown App")
        desc = app.get("description", "No description available.")
        download_url = app.get("download_url", "#")
        github_url = app.get("github_url", "#")
        screenshots = app.get("screenshots", [])

        caption = (
            f"📱 **{name}**\n\n"
            f"📝 **Description:**\n{desc}\n\n"
            f"🔗 [GitHub Source]({github_url}) | 📥 [Download Release]({download_url})"
        )

        if screenshots:
            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=screenshots[0],
                    caption=caption,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send image: {e}")
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=caption,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=caption,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )

    keyboard = [[InlineKeyboardButton("🔙 Back to Categories", callback_data="main_menu")]]
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✨ End of list.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is missing!")
        return

    # Start Health Check HTTP server in a daemon thread for Render
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Build Telegram Bot Application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add Command & Callback Query Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))

    logger.info("Bot started successfully...")
    
    # Run polling loop (Compatible with python-telegram-bot v21+)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
