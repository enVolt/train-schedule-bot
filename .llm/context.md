# Project Context: Train Schedule Telegram Bot

## Overview
This is a Python-based project that provides real-time UK train schedules via a Telegram bot and a REST API. It uses the National Rail Darwin Live Departure Board Web Service (LDBWS).

## Tech Stack
- **Language**: Python 3.x
- **Bot Framework**: `python-telegram-bot` (v20+)
- **API Framework**: `FastAPI` (v0.110+)
- **Process Manager**: `PM2`
- **Database**: SQLite (via a custom `SQLitePersistence` class)
- **API**: National Rail SOAP API (Darwin LDBWS)
- **Environment**: `python-dotenv` for secret management

## Core Components
- `bot.py`: Entry point for the Telegram bot, command handlers, and UI logic.
- `api.py`: Entry point for the REST API service (FastAPI).
- `national_rail_api.py`: Logic for fetching raw train data and formatting it for different clients.
- `sqlite_persistence.py`: Custom persistence layer for `python-telegram-bot` using SQLite.
- `scheduler.py`: Logic for timed notifications.
- `ecosystem.config.js`: PM2 configuration for managing the bot and API processes.

## Persistence Model
The bot uses a SQLite database (`bot_data.db`) to store user settings like `home_crs`, `office_crs`, and scheduled slots. This is implemented in `sqlite_persistence.py` to ensure data persistence across bot restarts and to allow safe asynchronous access.

## Configuration
Requires a `.env` file with:
- `TELEGRAM_BOT_TOKEN`: Token from @BotFather.
- `NATIONAL_RAIL_API_TOKEN`: Token from National Rail Open Data.
- `AUTHORIZED_USER_IDS`: (Optional) Comma-separated list of Telegram User IDs allowed to use the bot.
