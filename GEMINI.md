# Gemini CLI Project Instructions

This project uses an agent-independent `.llm` directory for context. Please refer to these files for project understanding and development guidelines.

- [Project Context](.llm/context.md)
- [Development Instructions](.llm/instructions.md)

## Key Commands
- Start everything (PM2): `pm2 start ecosystem.config.js`
- Restart everything: `pm2 restart ecosystem.config.js`
- View logs: `pm2 logs`
- Run tests: `python test_bot.py`
