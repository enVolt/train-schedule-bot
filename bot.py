import os
import logging
import asyncio
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from sqlite_persistence import SQLitePersistence
from national_rail_api import fetch_train_schedule

# Load environment variables
load_dotenv()

# --- Configuration ---
NATIONAL_RAIL_API_TOKEN = os.getenv("NATIONAL_RAIL_API_TOKEN")
USER_AGENT = os.getenv("USER_AGENT", "train-bot-app/0.0.1") # Default user agent

# --- Authorization Setup ---
AUTHORIZED_USER_IDS_STR = os.getenv("AUTHORIZED_USER_IDS", "")
if not AUTHORIZED_USER_IDS_STR:
    logging.warning("AUTHORIZED_USER_IDS is not set. The bot will be open to everyone.")
    AUTHORIZED_USER_IDS = set()
else:
    AUTHORIZED_USER_IDS = {int(user_id.strip()) for user_id in AUTHORIZED_USER_IDS_STR.split(',') if user_id.strip()}

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def restricted(func):
    """
    Restricts access to a command handler to authorized user IDs.
    If the list of authorized IDs is empty, the bot is considered public.
    """
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if AUTHORIZED_USER_IDS and user_id not in AUTHORIZED_USER_IDS:
            logging.warning(f"Unauthorized access denied for user_id {user_id}.")
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and explains the bot's functionality."""
    user_id = update.effective_user.id
    if AUTHORIZED_USER_IDS and user_id not in AUTHORIZED_USER_IDS:
        logging.warning(f"Unauthorized user {user_id} tried to start the bot.")
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot.\n"
            f"If you'd like to request access, please provide the admin with your User ID: `{user_id}`"
        )
        return

    welcome_text = (
        "Welcome to the Train Schedule Bot!\n\n"
        "I can help you check train schedules for your commute.\n\n"
        "**Configuration:**\n"
        "/set_home <CRS> - Set your home station (e.g., /set_home KGX)\n"
        "/set_office <CRS> - Set your office station (e.g., /set_office EUS)\n\n"
        "**On-Demand Schedules:**\n"
        "/now - Get schedule now (choose direction).\n"
        "/nowt - Get schedule: Home to Office.\n"
        "/nowf - Get schedule: Office to Home.\n\n"
        "**Scheduled Notifications:**\n"
        "/set_to_slot <HH:mm AM/PM> - Schedule morning commute (e.g., /set_to_slot 08:30 AM)\n"
        "/set_from_slot <HH:mm AM/PM> - Schedule evening commute (e.g., /set_from_slot 05:30 PM)\n"
    )
    await update.message.reply_text(welcome_text)

@restricted
async def set_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the user's home station."""
    try:
        crs_code = context.args[0].upper()
        if len(crs_code) != 3 or not crs_code.isalpha():
            raise ValueError
        context.user_data['home_crs'] = crs_code
        await update.message.reply_text(f"Home station set to {crs_code}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /set_home <3_LETTER_CRS_CODE>")

@restricted
async def set_office(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the user's office station."""
    try:
        crs_code = context.args[0].upper()
        if len(crs_code) != 3 or not crs_code.isalpha():
            raise ValueError
        context.user_data['office_crs'] = crs_code
        await update.message.reply_text(f"Office station set to {crs_code}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /set_office <3_LETTER_CRS_CODE>")

async def _set_slot(update: Update, context: ContextTypes.DEFAULT_TYPE, slot_type: str) -> None:
    """Helper function to set a time slot."""
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(f"Usage: /set_{slot_type}_slot <HH:mm AM/PM>")
        return

    time_str = f"{context.args[0]} {context.args[1].upper()}"
    try:
        # Validate the time format
        datetime.strptime(time_str, "%I:%M %p")
        context.user_data[f'{slot_type}_slot'] = time_str
        await update.message.reply_text(f"Notification for '{slot_type}' commute set to {time_str}.")
    except ValueError:
        await update.message.reply_text("Invalid time format. Please use HH:mm AM/PM (e.g., 08:30 AM).")

@restricted
async def set_to_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the morning commute time slot (home to office)."""
    await _set_slot(update, context, "to")

@restricted
async def set_from_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the evening commute time slot (office to home)."""
    await _set_slot(update, context, "from")

@restricted
async def now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides an on-demand schedule."""
    home_crs = context.user_data.get('home_crs')
    office_crs = context.user_data.get('office_crs')

    if not home_crs or not office_crs:
        await update.message.reply_text("Please set both home and office CRS codes first.")
        return

    keyboard = [
        [InlineKeyboardButton("Home -> Office", callback_data='home_to_office')],
        [InlineKeyboardButton("Office -> Home", callback_data='office_to_home')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Please choose a direction:', reply_markup=reply_markup)

@restricted
async def nowt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gets the train schedule from Home to Office."""
    home_crs = context.user_data.get('home_crs')
    office_crs = context.user_data.get('office_crs')

    if not home_crs or not office_crs:
        await update.message.reply_text("Please set both home and office CRS codes first using /set_home and /set_office.")
        return

    route_text = "Home to Office"
    await update.message.reply_text(f"Fetching schedule for {route_text}...")
    
    schedule_text = await fetch_train_schedule(NATIONAL_RAIL_API_TOKEN, USER_AGENT, home_crs, office_crs)
    await update.message.reply_text(schedule_text)

@restricted
async def nowf_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gets the train schedule from Office to Home."""
    home_crs = context.user_data.get('home_crs')
    office_crs = context.user_data.get('office_crs')

    if not home_crs or not office_crs:
        await update.message.reply_text("Please set both home and office CRS codes first using /set_home and /set_office.")
        return

    route_text = "Office to Home"
    await update.message.reply_text(f"Fetching schedule for {route_text}...")
    
    schedule_text = await fetch_train_schedule(NATIONAL_RAIL_API_TOKEN, USER_AGENT, office_crs, home_crs)
    await update.message.reply_text(schedule_text)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button presses for the /now command."""
    query = update.callback_query
    user_id = query.from_user.id

    # Restrict access for callback queries as well
    if AUTHORIZED_USER_IDS and user_id not in AUTHORIZED_USER_IDS:
        logging.warning(f"Unauthorized access denied for user_id {user_id} via callback query.")
        await query.answer("Sorry, you are not authorized to use this bot.", show_alert=True)
        return

    await query.answer()

    home_crs = context.user_data.get('home_crs')
    office_crs = context.user_data.get('office_crs')

    if query.data == 'home_to_office':
        origin, destination = home_crs, office_crs
        route_text = "Home to Office"
    elif query.data == 'office_to_home':
        origin, destination = office_crs, home_crs
        route_text = "Office to Home"
    else:
        await query.edit_message_text(text="Invalid selection.")
        return

    await query.edit_message_text(text=f"Fetching schedule for {route_text}...")
    
    schedule_text = await fetch_train_schedule(NATIONAL_RAIL_API_TOKEN, USER_AGENT, origin, destination)
    await context.bot.send_message(chat_id=query.message.chat_id, text=schedule_text)


# --- Main Application Setup ---

def main() -> None:
    """Run the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    # Set up persistence with the new SQLite-based class.
    persistence = SQLitePersistence(filepath="bot_data.db")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(token).persistence(persistence).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_home", set_home))
    application.add_handler(CommandHandler("set_office", set_office))
    application.add_handler(CommandHandler("now", now))
    application.add_handler(CommandHandler("nowt", nowt_command))
    application.add_handler(CommandHandler("nowf", nowf_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler("set_to_slot", set_to_slot))
    application.add_handler(CommandHandler("set_from_slot", set_from_slot))

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
