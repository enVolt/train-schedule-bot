module.exports = {
  apps: [
    {
      name: 'train-api',
      script: 'api.py',
      interpreter: 'python3',
      env: {
        NODE_ENV: 'development',
      },
      env_production: {
        NODE_ENV: 'production',
      }
    },
    {
      name: 'train-bot',
      script: 'bot.py',
      interpreter: 'python3',
      env: {
        NODE_ENV: 'development',
      },
      env_production: {
        NODE_ENV: 'production',
      }
    }
  ],
};
