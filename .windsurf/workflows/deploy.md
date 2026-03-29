---
description: How to deploy the Exam Paper Bot to HuggingFace Spaces
tags: [deployment, huggingface, telegram-bot]
---

# Deploy Exam Paper Bot to HuggingFace

## Prerequisites
1. HuggingFace account (free)
2. Telegram Bot Token (from @BotFather)

## Step 1: Create HuggingFace Space
1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Select:
   - **Space name**: `your-exam-bot` (or any unique name)
   - **License**: MIT (or your preference)
   - **Space SDK**: Select "Blank" or "Python"
   - **Visibility**: Public (or Private)
4. Click "Create Space"

## Step 2: Upload Files
Upload these files to your HuggingFace Space:
- `main.py` - Your bot code
- `requirements.txt` - Python dependencies
- `README.md` - (optional)

### Or use Git to push:
```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/your-exam-bot
cd your-exam-bot
# Copy your files here
git add .
git commit -m "Initial bot upload"
git push
```

## Step 3: Set Environment Variables (IMPORTANT!)
In your HuggingFace Space:
1. Go to **Settings** tab
2. Click **Variables and Secrets**
3. Add new secret:
   - **Name**: `TELEGRAM_BOT_TOKEN`
   - **Value**: Your bot token from @BotFather (e.g., `123456789:ABCdefGHIjklMNOpqrSTUvwxyz`)
4. Click **Save**

## Step 4: Configure the Space to Stay Alive
In **Settings** tab:
1. Set **Sleep Timeout** to `Never` (for free tier, it may still sleep after 48h of inactivity)
2. The bot has built-in self-ping mechanism to keep it awake

## Step 5: Wait and Test
1. Wait 2-3 minutes for the Space to build
2. Check the **Logs** tab for any errors
3. Open your Telegram bot and send `/start`
4. Try selecting an exam and year to test PDF download

## Troubleshooting

### Bot not responding?
- Check **Logs** in HuggingFace Space
- Verify `TELEGRAM_BOT_TOKEN` is set correctly (no quotes, no spaces)
- Ensure the token format is correct: `123456789:ABC...`

### PDF download not working?
- The bot tries multiple sources automatically
- If auto-download fails, use the manual "Try Download" buttons
- Some sites block cloud IPs - the bot will provide direct links

### Space sleeping?
- Free tier spaces sleep after 48h inactivity
- The bot has auto-ping, but you can also:
  - Visit the Space URL periodically
  - Use a 3rd party uptime monitor (like UptimeRobot) to ping every 5 minutes

## Updating the Bot
When you make changes to `main.py`:
1. Upload the new file to HuggingFace Space
2. Or push via git:
   ```bash
   git add main.py
   git commit -m "Updated bot"
   git push
   ```
3. HuggingFace will automatically rebuild and restart

## Files Overview
- `main.py` - Main bot code with all handlers and PDF download logic
- `requirements.txt` - Required Python packages
  ```
  python-telegram-bot>=20.0
  beautifulsoup4
  aiohttp
  duckduckgo-search
  primp
  python-dotenv
  requests
  ```

## Support
If issues persist, check:
1. Telegram Bot Token is valid (test with @BotFather)
2. All dependencies in requirements.txt are correct
3. Space has at least 2GB RAM (check in Settings)
