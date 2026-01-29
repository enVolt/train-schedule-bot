import os
import logging
import asyncio
import sqlite3
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from national_rail_api import fetch_train_schedule

# --- Setup ---
load_dotenv() # Load environment variables at the very beginning

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load API token and User Agent globally for use by scheduled jobs
NATIONAL_RAIL_API_TOKEN = os.getenv('NATIONAL_RAIL_API_TOKEN')
USER_AGENT = os.getenv("USER_AGENT", "train-bot-scheduler/0.0.1") # Default user agent for scheduler

RESYNC_INTERVAL_MINUTES = 5 # How often the scheduler re-reads the database for schedule changes


async def send_schedule_notification(bot: telegram.Bot, chat_id: int, origin_crs: str, destination_crs: str):
    """Fetches and sends a single schedule notification."""
    logger.info(f"Sending schedule for chat_id {chat_id}: {origin_crs} -> {destination_crs}")
    if not NATIONAL_RAIL_API_TOKEN:
        logger.error("NATIONAL_RAIL_API_TOKEN not found. Cannot fetch schedule.")
        await bot.send_message(chat_id=chat_id, text="Error: National Rail API token is not configured for the scheduler.")
        return

    try:
        message = await fetch_train_schedule(NATIONAL_RAIL_API_TOKEN, USER_AGENT, origin_crs, destination_crs)
        await bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logger.error(f"Failed to send notification to chat_id {chat_id}: {e}")
        await bot.send_message(chat_id=chat_id, text=f"Error fetching schedule: {e}")


async def get_all_user_data() -> list:
    """Connects to the SQLite DB and fetches all user data asynchronously."""
    db_path = 'bot_data.db'
    def sync_get_data():
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("SELECT user_id, data FROM user_data")
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Database error while fetching user data: {e}")
            return []
    
    return await asyncio.to_thread(sync_get_data)


async def resync_all_user_schedules(bot: telegram.Bot, scheduler: AsyncIOScheduler):
    """
    Fetches all user data from the database and updates/adds schedules to the APScheduler.
    Uses replace_existing=True to handle updates to user schedules.
    """
    logger.info("Resyncing all user schedules from the database...")
    users = await get_all_user_data()
    if not users:
        logger.info("No users found in the database during resync.")
        # Optionally, remove all existing jobs if no users are found
        # for job in scheduler.get_jobs():
        #     if job.id.startswith("user_"): # Assuming user jobs start with "user_"
        #         scheduler.remove_job(job.id)
        return

    current_job_ids = set() # To keep track of jobs we've just scheduled

    for user_id, data_json in users:
        try:
            user_data = json.loads(data_json)
            home_crs = user_data.get('home_crs')
            office_crs = user_data.get('office_crs')

            if not home_crs or not office_crs:
                logger.info(f"Skipping scheduling for user {user_id}: home or office CRS not set.")
                continue
            
            chat_id = user_id # Assuming chat_id is the same as user_id for direct messages

            for slot_type, origin_crs, dest_crs in [('to_slot', home_crs, office_crs), ('from_slot', office_crs, home_crs)]:
                slot_time_str = user_data.get(slot_type)
                if slot_time_str:
                    slot_time = datetime.strptime(slot_time_str, "%I:%M %p").time()

                    job_id_1 = f"{user_id}_{slot_type}_1"
                    scheduler.add_job(
                        send_schedule_notification,
                        'cron',
                        day_of_week='mon-fri', # Schedule only on weekdays
                        hour=slot_time.hour,
                        minute=slot_time.minute,
                        args=[bot, chat_id, origin_crs, dest_crs],
                        id=job_id_1,
                        replace_existing=True # Crucial for updating schedules
                    )
                    current_job_ids.add(job_id_1)

                    second_notification_dt = (datetime.combine(datetime.today(), slot_time) + timedelta(minutes=30))
                    second_notification_time = second_notification_dt.time()
                    
                    job_id_2 = f"{user_id}_{slot_type}_2"
                    scheduler.add_job(
                        send_schedule_notification,
                        'cron',
                        day_of_week='mon-fri', # Schedule only on weekdays
                        hour=second_notification_time.hour,
                        minute=second_notification_time.minute,
                        args=[bot, chat_id, origin_crs, dest_crs],
                        id=job_id_2,
                        replace_existing=True # Crucial for updating schedules
                    )
                    current_job_ids.add(job_id_2)
                    logger.info(f"Scheduled '{slot_type}' for user {user_id} (chat {chat_id}) at {slot_time.strftime('%H:%M')} and {second_notification_time.strftime('%H:%M')} (weekdays).")

        except json.JSONDecodeError:
            logger.error(f"Could not parse user_data JSON for user_id {user_id}. Skipping.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while scheduling for user {user_id}: {e}. Skipping.")

    # Remove any jobs that are no longer in the database (e.g., user deleted schedule)
    for job in scheduler.get_jobs():
        if job.id.startswith(f"{user_id}_") and job.id not in current_job_ids:
            scheduler.remove_job(job.id)
            logger.info(f"Removed stale job: {job.id}")


async def main():
    """Main function to set up and run the scheduler."""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables. Exiting.")
        return
    
    if not NATIONAL_RAIL_API_TOKEN:
        logger.error("NATIONAL_RAIL_API_TOKEN not found in environment variables. Scheduled notifications will fail.")

    bot = telegram.Bot(token=bot_token)
    scheduler = AsyncIOScheduler()
    logger.info(f"Scheduler starting with timezone: {scheduler.timezone}")

    # Initial load of all schedules
    await resync_all_user_schedules(bot, scheduler)

    # Schedule periodic re-sync
    scheduler.add_job(
        resync_all_user_schedules,
        'interval',
        minutes=RESYNC_INTERVAL_MINUTES,
        args=[bot, scheduler],
        id='resync_job',
        replace_existing=True
    )
    logger.info(f"Scheduled periodic resync every {RESYNC_INTERVAL_MINUTES} minutes.")


    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to exit.")

    # Keep the script running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour, the scheduler runs in the background
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler shut down.")


if __name__ == "__main__":
    asyncio.run(main())
