---
title: Exam Assistant Bot
emoji: 📚
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Exam Assistant Bot v11.0 LIVE 📚

Ek simple Telegram bot jo students ko **Previous Year Question Papers (PYQ)** PDF format mein dhoondne mein help karta hai.

## ✨ Features
- **Direct Search**: Kisi bhi subject ya exam ka naam likhein (जैसे: `Class 10 CBSE Maths 2022`).
- **PDF Preference**: Ye bot online direct PDF links ko dhoondne ki koshish karta hai.
- **Easy Interface**: JEE, NEET, CBSE, SSC jaise exams ke liye buttons.
- **Free & Fast**: Bina kisi database ke live search.

## 🚀 Setup & Run (Local)

1. **Bot Token**: [BotFather](https://t.me/BotFather) ke paas jayein aur apna naya bot create karke **API Token** copy karein.
2. **Environment Variable**: `.env.example` file ko rename karke `.env` banayein aur apna token paste karein.
   ```text
   TELEGRAM_BOT_TOKEN=7xxx:xxxx-xxxx
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the Bot**:
   ```bash
   python main.py
   ```

## 🛠 Tech Stack
- **Python 3.10+**
- **python-telegram-bot** (Bot development)
- **googlesearch-python** (Real-time web search for PDFs)
- **python-dotenv** (Secret management)

---
Developed for Students by Ayush Verma
