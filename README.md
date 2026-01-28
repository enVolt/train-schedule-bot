# Train Schedule Telegram Bot

This is a Telegram bot designed to provide real-time UK train schedules. It allows users to save their home and office station codes and fetch schedules on-demand.

## Core Features

*   **Station Configuration**: Set and save your home and office stations using 3-letter CRS codes.
*   **On-Demand Schedules**:
    *   Use `/now` to interactively choose your direction of travel.
    *   Use `/nowt` for a direct "Home to Office" schedule.
    *   Use `/nowf` for a direct "Office to Home" schedule.
*   **Persistent User Data**: User settings are stored in a robust SQLite database (`bot_data.db`), ensuring data is not lost on restart.

## Technical Details

*   **Framework**: Built with the `python-telegram-bot` library.
*   **API Integration**: Fetches real-time train data from the National Rail Live Departure Board API.
*   **Persistence**: Uses a custom, asynchronous `SQLitePersistence` class to safely store user data in a `bot_data.db` file. This allows for safe, multi-process access, laying the groundwork for a separate scheduler process.
*   **Configuration**: Requires a `.env` file for storing API tokens.

## Available Commands

*   `/start`: Displays a welcome message and a list of available commands.
*   `/set_home <CRS_CODE>`: Sets your home station (e.g., `/set_home KGX`).
*   `/set_office <CRS_CODE>`: Sets your office station (e.g., `/set_office EUS`).
*   `/now`: Asks for your desired travel direction and provides the schedule.
*   `/nowt`: Provides a "Home to Office" schedule directly.
*   `/nowf`: Provides an "Office to Home" schedule directly.

## Setup and Running

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Create an environment file:**
    *   Create a file named `.env` in the root directory.
    *   Add your API tokens to this file:
      ```
      TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
      NATIONAL_RAIL_API_TOKEN="YOUR_NATIONAL_RAIL_API_TOKEN"
      ```

4.  **Run the bot:**
    ```bash
    python bot.py
    ```

The bot will start, and a `bot_data.db` file will be created to store user data.

---
Vibe coded with help of Gemini.