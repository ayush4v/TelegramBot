import asyncio
from telegram import Bot
import os

async def set_photo():
    token = "8618692434:AAHJwI0-s8IlFlsLoLq8dWjNEuCAUOdWL9s"
    photo_path = r"C:\Users\ayush\.gemini\antigravity\brain\7d40a57b-cc27-4a24-9d5b-95e379af0937\exam_bot_logo_professional_1774207476836.png"
    bot = Bot(token=token)
    try:
        with open(photo_path, 'rb') as photo:
            # chat_id for setting bot's own photo usually doesn't work via this method
            # but I'll try it once. If not, it needs BotFather.
            await bot.set_chat_photo(chat_id="8618692434", photo=photo)
            print("Successfully set bot photo!")
    except Exception as e:
        print(f"Failed to set bot photo: {e}")

if __name__ == "__main__":
    asyncio.run(set_photo())
