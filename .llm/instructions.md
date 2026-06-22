# Development Instructions

## Coding Standards
- **Style**: Follow PEP 8 guidelines.
- **Asynchrony**: Use `async`/`await` consistently. The bot framework and database persistence are built on `asyncio`.
- **Error Handling**: Use `try/except` blocks in command handlers to provide user-friendly error messages via Telegram.
- **Logging**: Use the standard `logging` library. Log important events (unauthorized access, API failures) at appropriate levels.

## Database Modifications
- Any changes to the user data structure must be reflected in `sqlite_persistence.py`.
- Ensure migrations or table creations are handled during initialization if the schema changes.

## API Integration
- Keep `national_rail_api.py` focused on data retrieval and parsing.
- UI formatting (how the data looks in Telegram) should happen in `bot.py` or a dedicated formatting module.
- Always respect the `AUTHORIZED_USER_IDS` configuration to prevent unauthorized bot usage.

## Technical Integrity
- The project uses PM2 for process management. Use `pm2 start ecosystem.config.js` to run both the bot and the API.
- The API runs on port 8000 by default and exposes `GET /api/schedule`.

## Testing
- Add tests to `test_bot.py` for any new logic.
- Mock external API calls (National Rail and Telegram) during unit tests.
