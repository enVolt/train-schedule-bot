import os
import logging
import asyncio
from functools import wraps
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from sqlite_persistence import SQLitePersistence
import requests

# Load environment variables
load_dotenv()

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
        "Here are the commands to get started:\n"
        "/set_home <CRS_CODE> - Set your home station (e.g., /set_home KGX)\n"
        "/set_office <CRS_CODE> - Set your office station (e.g., /set_office EUS)\n"
        "/now - Get the latest train schedule on-demand (choose direction).\n"
        "/nowt - Get the latest train schedule: Home to Office.\n"
        "/nowf - Get the latest train schedule: Office to Home.\n"
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
    
    schedule_text = await fetch_train_schedule(home_crs, office_crs)
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
    
    schedule_text = await fetch_train_schedule(office_crs, home_crs)
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
    
    schedule_text = await fetch_train_schedule(origin, destination)
    await context.bot.send_message(chat_id=query.message.chat_id, text=schedule_text)


# --- Helper Functions & API Logic ---

async def fetch_train_schedule(origin: str, destination: str) -> str:
    """Fetches the train schedule from the National Rail API using the official REST endpoint."""
    api_token = os.getenv("NATIONAL_RAIL_API_TOKEN")
    if not api_token:
        return "NATIONAL_RAIL_API_TOKEN not found in environment variables."

    url = f"https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/20220120/GetDepBoardWithDetails/{origin}"
    params = {
        "filterCrs": destination,
        "filterType": "to",
        "numRows": 10,
        "timeWindow": 120,
    }
    headers = {
        "x-apikey": api_token,
        'user-agent': 'ashwani-my-app/0.0.1'
    }

    try:
        response = await asyncio.to_thread(requests.get, url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data or not data.get("trainServices"):
            return f"No direct services found from {origin} to {destination} at this time."

        schedule_lines = [f"Trains from {origin} to {destination}:\n"]
        for service in data["trainServices"]:
            std = service.get("std")
            etd = service.get("etd")
            platform = service.get("platform", "TBA")
            operator = service.get("operator")
            is_cancelled = service.get("isCancelled", False)

            status = f"{std} -> {etd}"
            if etd and etd.lower() != 'on time':
                status = f"{std} (exp. {etd})"
            if is_cancelled:
                status = f"{std} - CANCELLED"

            schedule_lines.append(
                f"- {status}, Plat: {platform}, Op: {operator}"
            )
        
        return "\n".join(schedule_lines)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error(f"Authentication error: {e}")
            return "Authentication failed. Please check your API token."
        logger.error(f"HTTP error fetching train schedule: {e}")
        return f"Sorry, there was a problem reaching the schedule service (HTTP {e.response.status_code})."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching train schedule: {e}")
        return "Sorry, I couldn't connect to the train schedule service."
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return "An unexpected error occurred while fetching the schedule."


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

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
