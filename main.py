import asyncio
import logging
import os
import io
import aiohttp
from typing import List, Dict, Tuple

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from bs4 import BeautifulSoup
import urllib.parse
from aiohttp import web
from duckduckgo_search import DDGS
import threading
import requests
import time
import primp

# Load variables from .env or .env.token
if os.path.exists(".env"):
    load_dotenv(".env")
elif os.path.exists(".env.token"):
    load_dotenv(".env.token")
else:
    load_dotenv()

# Logger settings
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
BOT_VERSION = "v12.3 Stable-Push"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger.info(f"🛠 Loading ExamBot {BOT_VERSION}...")

# Expanded Exam Categories
EXAM_CATEGORIES = {
    "🛠 Engineering": {
        "JEE Mains": "JEE Mains Previous Year Question Paper",
        "JEE Advanced": "JEE Advanced Previous Year Question Paper",
        "GATE": "GATE Previous Year Question Paper",
        "BITSAT": "BITSAT Exam Question Paper",
        "WBJEE": "WBJEE Previous Year Paper",
        "WBJEE JELET": "WBJEE JELET Previous Year Question Paper",
        "WBJEE JENPAS": "WBJEE JENPAS UG Question Paper",
        "MHT CET": "MHT CET Exam Result Question Paper",
    },
    "🩺 Medical": {
        "NEET UG": "NEET UG Previous Year Question Paper",
        "NEET PG": "NEET PG Previous Year Paper",
        "AIIMS": "AIIMS Previous Year Solved Paper",
        "JIPMER": "JIPMER Medical Entrance Question Paper",
    },
    "🇮🇳 Govt Job (UPSC/SSC)": {
        "UPSC CSE (IAS)": "UPSC CSE Prelims Mains Question Paper",
        "SSC CGL": "SSC CGL Tier 1 Tier 2 Previous Year Paper",
        "SSC CHSL": "SSC CHSL Exam Question Paper",
        "IBPS PO": "IBPS PO Bank Exam Question Paper",
        "SBI PO": "SBI PO Previous Year Paper",
        "RRB NTPC": "RRB NTPC Exam Question Paper",
        "NDA/CDS": "NDA CDS Previous Year Question Paper",
    },
    "🏫 School Boards": {
        "CBSE Class 10": "CBSE Class 10 Previous Year Question Paper",
        "CBSE Class 12": "CBSE Class 12 Previous Year Question Paper",
        "ICSE Class 10": "ICSE Class 10 Previous Year Paper",
        "ISC Class 12": "ISC Class 12 Exam Question Paper",
        "NIOS": "NIOS Board Previous Year Paper",
        "UP Board": "UP Board Class 10 12 Question Paper",
        "Bihar Board": "Bihar Board Exam Question Paper",
    },
    "🎓 MBA/Law/Others": {
        "CAT": "CAT Exam Previous Year Question Paper",
        "CLAT": "CLAT Law Entrance Question Paper",
        "NIFT": "NIFT Design Entrance Paper",
        "CUET": "CUET UG PG Exam Question Paper",
        "DU LLB": "DU LLB Entrance Exam Question Paper",
    }
}

YEARS = ["2024", "2023", "2022", "2021", "2020", "2019", "2018", "Older"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows main categories."""
    text = (
        f"👋 **Welcome to the One-Click Exam Paper Bot {BOT_VERSION}**\n\n"
        "I provide **Direct PDF Downloads** for all major Indian exams (JEE, NEET, SSC, UPSC, CBSE, etc.) directly in this chat.\n\n"
        "❌ **No more annoying links or redirects!**\n\n"
        "Please select a **Category** below to receive your paper instantly:"
    )
    keyboard = []
    categories = list(EXAM_CATEGORIES.keys())
    for cat in categories:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat|{cat}")])
    
    keyboard.append([InlineKeyboardButton("🔍 Direct Search (Type Any Exam)", callback_data="direct_search")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows exams in a category."""
    query = update.callback_query
    await query.answer()
    # Handle with pipes
    cat_name = query.data.split("|")[1]
    exams = EXAM_CATEGORIES.get(cat_name, {})
    
    text = f"📂 **Category: {cat_name}**\n\nNow, select a specific **Exam** from the list below:"
    keyboard = []
    exam_names = list(exams.keys())
    cat_key = cat_name.replace(" ", "_")
    for i in range(0, len(exam_names), 2):
        row = [InlineKeyboardButton(exam_names[i], callback_data=f"exam|{cat_name}|{exam_names[i]}")]
        if i+1 < len(exam_names):
            row.append(InlineKeyboardButton(exam_names[i+1], callback_data=f"exam|{cat_name}|{exam_names[i+1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="back_cats")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def exam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows years for a specific exam."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")
    cat_name = parts[1]
    exam_name = parts[2]
    
    text = f"🎯 **Selected Exam: {exam_name}**\n\nWhich **Academic Year** paper are you looking for?"
    keyboard = []
    for i in range(0, len(YEARS), 2):
        row = [InlineKeyboardButton(YEARS[i], callback_data=f"year|{cat_name}|{exam_name}|{YEARS[i]}")]
        if i+1 < len(YEARS):
            row.append(InlineKeyboardButton(YEARS[i+1], callback_data=f"year|{cat_name}|{exam_name}|{YEARS[i+1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Exams", callback_data=f"cat|{cat_name}")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Global Session for performance
session_instance: aiohttp.ClientSession = None

async def get_session():
    global session_instance
    if session_instance is None or session_instance.closed:
        # Create session with SSL verification DISABLED and CookieJar enabled
        # This is essential for sites that use landing pages to set session cookies
        conn = aiohttp.TCPConnector(ssl=False)
        jar = aiohttp.CookieJar(unsafe=True)
        timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
        session_instance = aiohttp.ClientSession(connector=conn, cookie_jar=jar, timeout=timeout)
    return session_instance


# Rotating profiles and user-agents
IMPERSONATES = ["chrome_123", "chrome_110", "safari_17", "edge_119"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

async def search_ecosia(query: str, limit: int = 5) -> List[dict]:
    """Ecosia: Often less bot-detection than Google/Bing on cloud IPs."""
    results = []
    try:
        async with primp.AsyncClient(impersonate=random.choice(IMPERSONATES)) as client:
            encoded_q = urllib.parse.quote(f"{query} pdf")
            url = f"https://www.ecosia.org/search?q={encoded_q}"
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            resp = await client.get(url, timeout=12, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Ecosia search results are usually in article.result-card
                for card in soup.select('article.result'):
                    a = card.select_one('a.result-title')
                    if a and a.get('href', '').startswith('http'):
                        results.append({"title": a.get_text()[:80], "url": a['href']})
                    if len(results) >= limit: break
    except Exception as e:
        logger.warning(f"Ecosia search error: {e}")
    return results

async def search_google(query: str, limit: int = 5) -> List[dict]:
    """Scrape Google Search (Standard) with multiple selector patterns."""
    results = []
    try:
        async with primp.AsyncClient(impersonate=random.choice(IMPERSONATES)) as client:
            encoded_q = urllib.parse.quote(f"{query} pdf")
            url = f"https://www.google.com/search?q={encoded_q}&num=10"
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            resp = await client.get(url, timeout=12, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Try multiple common selectors
                selectors = ['div.g', 'div.yuRUbf', 'div.MjjYud']
                for selector in selectors:
                    for div in soup.select(selector):
                        a = div.select_one('a')
                        if a and a.get('href', '').startswith('http') and not "google.com" in a['href']:
                            title_tag = div.select_one('h3')
                            title = title_tag.get_text() if title_tag else "Search Result"
                            results.append({"title": title[:80], "url": a['href']})
                        if len(results) >= limit: break
                    if results: break # If first selector works, don't try others
    except Exception as e:
        logger.warning(f"Google search error: {e}")
    return results

async def search_bing(query: str, limit: int = 8) -> List[dict]:
    """Scrape Bing with enhanced resilience."""
    results = []
    try:
        async with primp.AsyncClient(impersonate=random.choice(IMPERSONATES)) as client:
            encoded_q = urllib.parse.quote(f"{query} pdf")
            url = f"https://www.bing.com/search?q={encoded_q}&count=15"
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            resp = await client.get(url, timeout=12, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for li in soup.select('li.b_algo'):
                    a_tag = li.select_one('h2 a')
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        if href and href.startswith('http'):
                            results.append({"title": title[:80], "url": href})
                    if len(results) >= limit: break
    except Exception as e:
        logger.warning(f"Bing error: {e}")
    return results

async def search_ddg_html(query: str, limit: int = 8) -> List[dict]:
    """Scrape DuckDuckGo HTML Lite."""
    results = []
    try:
        async with primp.AsyncClient(impersonate=random.choice(IMPERSONATES)) as client:
            encoded_q = urllib.parse.quote(f"{query} pdf")
            url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            resp = await client.get(url, timeout=12, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a_tag in soup.select('a.result__a'):
                    title = a_tag.get_text(strip=True)
                    href = a_tag.get('href', '')
                    if 'uddg=' in href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = urllib.parse.unquote(parsed.get('uddg', [''])[0])
                    
                    if href and href.startswith('http'):
                        results.append({"title": title[:80], "url": href})
                    if len(results) >= limit: break
    except Exception as e:
        logger.warning(f"DDG HTML error: {e}")
    return results


# ─────────────────────────────────────────────────────────────
# STATIC DATABASE — PRIMARY source, 100% reliable on Render!
# Keys are lowercase exam identifiers (with optional year)
# ─────────────────────────────────────────────────────────────
STATIC_DB: Dict[str, List[dict]] = {
    # ═══════════════════════════════════════════════════════════
    # JEE MAINS - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "jee mains 2024": [
        {"title": "JEE Main 2024 Jan & Apr Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2024/"},
        {"title": "JEE Main 2024 All Papers PDF - SelfStudys", "url": "https://www.selfstudys.com/jee-main-2024-question-paper"},
    ],
    "jee mains 2023": [
        {"title": "JEE Main 2023 Jan & Apr Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2023/"},
        {"title": "JEE Main 2023 Papers PDF", "url": "https://www.selfstudys.com/jee-main-2023-question-paper"},
    ],
    "jee mains 2022": [
        {"title": "JEE Main 2022 Jun & Jul Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2022/"},
        {"title": "JEE Main 2022 Papers PDF", "url": "https://www.selfstudys.com/jee-main-2022-question-paper"},
    ],
    "jee mains 2021": [
        {"title": "JEE Main 2021 Feb-Aug Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2021/"},
        {"title": "JEE Main 2021 Papers PDF", "url": "https://www.selfstudys.com/jee-main-2021-question-paper"},
    ],
    "jee mains 2020": [
        {"title": "JEE Main 2020 Jan & Sep Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2020/"},
        {"title": "JEE Main 2020 Papers PDF", "url": "https://www.selfstudys.com/jee-main-2020-question-paper"},
    ],
    "jee mains 2019": [
        {"title": "JEE Main 2019 Jan & Apr Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2019/"},
        {"title": "JEE Main 2019 Papers PDF", "url": "https://www.selfstudys.com/jee-main-2019-question-paper"},
    ],
    "jee mains 2018": [
        {"title": "JEE Main 2018 Offline & Online - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2018/"},
        {"title": "JEE Main 2018 Papers PDF", "url": "https://www.selfstudys.com/jee-main-2018-question-paper"},
    ],
    "jee mains": [
        {"title": "JEE Main All Years Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-question-papers/"},
        {"title": "JEE Main Previous Year Papers - Careers360", "url": "https://engineering.careers360.com/articles/jee-main-previous-year-question-papers"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # JEE ADVANCED - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "jee advanced 2024": [
        {"title": "JEE Advanced 2024 Paper 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2024/"},
        {"title": "JEE Advanced 2024 Papers PDF", "url": "https://www.selfstudys.com/jee-advanced-2024-question-paper"},
    ],
    "jee advanced 2023": [
        {"title": "JEE Advanced 2023 Paper 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2023/"},
        {"title": "JEE Advanced 2023 Papers PDF", "url": "https://www.selfstudys.com/jee-advanced-2023-question-paper"},
    ],
    "jee advanced 2022": [
        {"title": "JEE Advanced 2022 Paper 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2022/"},
        {"title": "JEE Advanced 2022 Papers PDF", "url": "https://www.selfstudys.com/jee-advanced-2022-question-paper"},
    ],
    "jee advanced 2021": [
        {"title": "JEE Advanced 2021 Paper 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2021/"},
        {"title": "JEE Advanced 2021 Papers PDF", "url": "https://www.selfstudys.com/jee-advanced-2021-question-paper"},
    ],
    "jee advanced 2020": [
        {"title": "JEE Advanced 2020 Paper 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2020/"},
        {"title": "JEE Advanced 2020 Papers PDF", "url": "https://www.selfstudys.com/jee-advanced-2020-question-paper"},
    ],
    "jee advanced 2019": [
        {"title": "JEE Advanced 2019 Paper 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2019/"},
    ],
    "jee advanced 2018": [
        {"title": "JEE Advanced 2018 Paper 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2018/"},
    ],
    "jee advanced": [
        {"title": "JEE Advanced All Years Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-question-papers/"},
        {"title": "JEE Advanced Previous Year Papers - Careers360", "url": "https://engineering.careers360.com/articles/jee-advanced-previous-year-question-papers"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # NEET UG - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "neet ug 2024": [
        {"title": "NEET UG 2024 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2024/"},
        {"title": "NEET 2024 Question Paper with Solutions", "url": "https://www.selfstudys.com/neet-2024-question-paper"},
    ],
    "neet ug 2023": [
        {"title": "NEET UG 2023 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2023/"},
        {"title": "NEET 2023 Question Paper", "url": "https://www.selfstudys.com/neet-2023-question-paper"},
    ],
    "neet ug 2022": [
        {"title": "NEET UG 2022 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2022/"},
        {"title": "NEET 2022 Question Paper", "url": "https://www.selfstudys.com/neet-2022-question-paper"},
    ],
    "neet ug 2021": [
        {"title": "NEET UG 2021 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2021/"},
        {"title": "NEET 2021 Question Paper", "url": "https://www.selfstudys.com/neet-2021-question-paper"},
    ],
    "neet ug 2020": [
        {"title": "NEET UG 2020 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2020/"},
        {"title": "NEET 2020 Question Paper", "url": "https://www.selfstudys.com/neet-2020-question-paper"},
    ],
    "neet ug 2019": [
        {"title": "NEET UG 2019 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2019/"},
        {"title": "NEET 2019 Question Paper", "url": "https://www.selfstudys.com/neet-2019-question-paper"},
    ],
    "neet ug 2018": [
        {"title": "NEET UG 2018 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2018/"},
        {"title": "NEET 2018 Question Paper", "url": "https://www.selfstudys.com/neet-2018-question-paper"},
    ],
    "neet ug": [
        {"title": "NEET All Years Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-question-papers/"},
        {"title": "NEET Previous Year Papers - Careers360", "url": "https://medicine.careers360.com/articles/neet-previous-year-question-papers"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # NEET PG
    # ═══════════════════════════════════════════════════════════
    "neet pg 2024": [{"title": "NEET PG 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-pg-2024/"}],
    "neet pg 2023": [{"title": "NEET PG 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-pg-2023/"}],
    "neet pg 2022": [{"title": "NEET PG 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-pg-2022/"}],
    "neet pg": [{"title": "NEET PG All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-pg-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # AIIMS
    # ═══════════════════════════════════════════════════════════
    "aiims 2024": [{"title": "AIIMS 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2024/"}],
    "aiims 2023": [{"title": "AIIMS 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2023/"}],
    "aiims 2022": [{"title": "AIIMS 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2022/"}],
    "aiims 2021": [{"title": "AIIMS 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2021/"}],
    "aiims 2020": [{"title": "AIIMS 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2020/"}],
    "aiims 2019": [{"title": "AIIMS 2019 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2019/"}],
    "aiims 2018": [{"title": "AIIMS 2018 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2018/"}],
    "aiims": [{"title": "AIIMS All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # JIPMER
    # ═══════════════════════════════════════════════════════════
    "jipmer": [{"title": "JIPMER Medical Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jipmer-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # GATE - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "gate 2024": [
        {"title": "GATE 2024 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2024/"},
        {"title": "GATE 2024 Papers PDF", "url": "https://www.selfstudys.com/gate-2024-question-paper"},
    ],
    "gate 2023": [
        {"title": "GATE 2023 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2023/"},
        {"title": "GATE 2023 Papers PDF", "url": "https://www.selfstudys.com/gate-2023-question-paper"},
    ],
    "gate 2022": [
        {"title": "GATE 2022 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2022/"},
        {"title": "GATE 2022 Papers PDF", "url": "https://www.selfstudys.com/gate-2022-question-paper"},
    ],
    "gate 2021": [
        {"title": "GATE 2021 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2021/"},
        {"title": "GATE 2021 Papers PDF", "url": "https://www.selfstudys.com/gate-2021-question-paper"},
    ],
    "gate 2020": [
        {"title": "GATE 2020 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2020/"},
    ],
    "gate 2019": [
        {"title": "GATE 2019 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2019/"},
    ],
    "gate 2018": [
        {"title": "GATE 2018 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2018/"},
    ],
    "gate": [
        {"title": "GATE All Years Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-question-papers/"},
        {"title": "GATE Previous Papers - MadeEasy", "url": "https://www.madeeasy.in/study-material/gate-previous-year-papers"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # BITSAT
    # ═══════════════════════════════════════════════════════════
    "bitsat": [
        {"title": "BITSAT Papers - AglaSem", "url": "https://schools.aglasem.com/tag/bitsat-question-papers/"},
        {"title": "BITSAT Previous Papers PDF", "url": "https://www.selfstudys.com/bitsat-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # WBJEE
    # ═══════════════════════════════════════════════════════════
    "wbjee 2024": [{"title": "WBJEE 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-2024/"}],
    "wbjee 2023": [{"title": "WBJEE 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-2023/"}],
    "wbjee 2022": [{"title": "WBJEE 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-2022/"}],
    "wbjee 2021": [{"title": "WBJEE 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-2021/"}],
    "wbjee 2020": [{"title": "WBJEE 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-2020/"}],
    "wbjee": [
        {"title": "WBJEE All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-question-papers/"},
        {"title": "WBJEE Previous Papers", "url": "https://www.selfstudys.com/wbjee-question-paper"},
    ],
    "wbjee jelet": [
        {"title": "WBJEE JELET Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-jelet-question-papers/"},
        {"title": "JELET Previous Papers - Examfare", "url": "http://www.examfare.com/p/jelet-previous-year-question-paper.html"},
    ],
    "wbjee jenpas": [{"title": "WBJEE JENPAS Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jenpas-ug-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # MHT CET
    # ═══════════════════════════════════════════════════════════
    "mht cet": [
        {"title": "MHT CET Papers - AglaSem", "url": "https://schools.aglasem.com/tag/mht-cet-question-papers/"},
        {"title": "MHT CET Previous Papers", "url": "https://www.selfstudys.com/mht-cet-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # UPSC CSE - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "upsc cse 2024": [
        {"title": "UPSC CSE 2024 Prelims & Mains - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2024/"},
        {"title": "UPSC 2024 Official Papers", "url": "https://upsc.gov.in/examinations/previous-question-papers"},
    ],
    "upsc cse 2023": [
        {"title": "UPSC CSE 2023 Prelims & Mains - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2023/"},
        {"title": "UPSC 2023 Official Papers", "url": "https://upsc.gov.in/examinations/previous-question-papers"},
    ],
    "upsc cse 2022": [
        {"title": "UPSC CSE 2022 Prelims & Mains - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2022/"},
    ],
    "upsc cse 2021": [
        {"title": "UPSC CSE 2021 Prelims & Mains - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2021/"},
    ],
    "upsc cse 2020": [
        {"title": "UPSC CSE 2020 Prelims & Mains - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2020/"},
    ],
    "upsc cse 2019": [
        {"title": "UPSC CSE 2019 Prelims & Mains - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2019/"},
    ],
    "upsc cse 2018": [
        {"title": "UPSC CSE 2018 Prelims & Mains - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2018/"},
    ],
    "upsc cse": [
        {"title": "UPSC CSE All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-question-papers/"},
        {"title": "UPSC Official Paper Archive", "url": "https://upsc.gov.in/examinations/previous-question-papers"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # SSC CGL - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "ssc cgl 2024": [
        {"title": "SSC CGL 2024 Tier 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2024/"},
        {"title": "SSC CGL 2024 Papers PDF", "url": "https://www.selfstudys.com/ssc-cgl-2024-question-paper"},
    ],
    "ssc cgl 2023": [
        {"title": "SSC CGL 2023 Tier 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2023/"},
        {"title": "SSC CGL 2023 Papers PDF", "url": "https://www.selfstudys.com/ssc-cgl-2023-question-paper"},
    ],
    "ssc cgl 2022": [
        {"title": "SSC CGL 2022 Tier 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2022/"},
        {"title": "SSC CGL 2022 Papers PDF", "url": "https://www.selfstudys.com/ssc-cgl-2022-question-paper"},
    ],
    "ssc cgl 2021": [
        {"title": "SSC CGL 2021 Tier 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2021/"},
        {"title": "SSC CGL 2021 Papers PDF", "url": "https://www.selfstudys.com/ssc-cgl-2021-question-paper"},
    ],
    "ssc cgl 2020": [
        {"title": "SSC CGL 2020 Tier 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2020/"},
    ],
    "ssc cgl 2019": [
        {"title": "SSC CGL 2019 Tier 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2019/"},
    ],
    "ssc cgl 2018": [
        {"title": "SSC CGL 2018 Tier 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2018/"},
    ],
    "ssc cgl": [
        {"title": "SSC CGL All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-question-papers/"},
        {"title": "SSC Official PYQ Portal", "url": "https://ssc.nic.in/Portal/Previous_Question_Paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # SSC CHSL - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "ssc chsl 2024": [{"title": "SSC CHSL 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2024/"}],
    "ssc chsl 2023": [{"title": "SSC CHSL 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2023/"}],
    "ssc chsl 2022": [{"title": "SSC CHSL 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2022/"}],
    "ssc chsl 2021": [{"title": "SSC CHSL 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2021/"}],
    "ssc chsl 2020": [{"title": "SSC CHSL 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2020/"}],
    "ssc chsl 2019": [{"title": "SSC CHSL 2019 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2019/"}],
    "ssc chsl 2018": [{"title": "SSC CHSL 2018 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2018/"}],
    "ssc chsl": [{"title": "SSC CHSL All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # IBPS PO - All Years
    # ═══════════════════════════════════════════════════════════
    "ibps po 2024": [{"title": "IBPS PO 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-2024/"}],
    "ibps po 2023": [{"title": "IBPS PO 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-2023/"}],
    "ibps po 2022": [{"title": "IBPS PO 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-2022/"}],
    "ibps po 2021": [{"title": "IBPS PO 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-2021/"}],
    "ibps po 2020": [{"title": "IBPS PO 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-2020/"}],
    "ibps po": [{"title": "IBPS PO All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # SBI PO - All Years
    # ═══════════════════════════════════════════════════════════
    "sbi po 2024": [{"title": "SBI PO 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-2024/"}],
    "sbi po 2023": [{"title": "SBI PO 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-2023/"}],
    "sbi po 2022": [{"title": "SBI PO 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-2022/"}],
    "sbi po 2021": [{"title": "SBI PO 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-2021/"}],
    "sbi po 2020": [{"title": "SBI PO 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-2020/"}],
    "sbi po": [{"title": "SBI PO All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # RRB NTPC - All Years
    # ═══════════════════════════════════════════════════════════
    "rrb ntpc 2024": [{"title": "RRB NTPC 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-2024/"}],
    "rrb ntpc 2023": [{"title": "RRB NTPC 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-2023/"}],
    "rrb ntpc 2022": [{"title": "RRB NTPC 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-2022/"}],
    "rrb ntpc 2021": [{"title": "RRB NTPC 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-2021/"}],
    "rrb ntpc 2020": [{"title": "RRB NTPC 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-2020/"}],
    "rrb ntpc": [{"title": "RRB NTPC All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # NDA - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "nda 2024": [
        {"title": "NDA 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2024/"},
        {"title": "NDA 2024 Official - UPSC", "url": "https://upsc.gov.in/examinations/previous-question-papers"},
    ],
    "nda 2023": [
        {"title": "NDA 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2023/"},
        {"title": "NDA 2023 Official - UPSC", "url": "https://upsc.gov.in/examinations/previous-question-papers"},
    ],
    "nda 2022": [{"title": "NDA 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2022/"}],
    "nda 2021": [{"title": "NDA 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2021/"}],
    "nda 2020": [{"title": "NDA 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2020/"}],
    "nda 2019": [{"title": "NDA 2019 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2019/"}],
    "nda 2018": [{"title": "NDA 2018 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2018/"}],
    "nda": [
        {"title": "NDA All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-question-papers/"},
        {"title": "NDA Official - UPSC", "url": "https://upsc.gov.in/examinations/previous-question-papers"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # CDS - All Years
    # ═══════════════════════════════════════════════════════════
    "cds 2024": [{"title": "CDS 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-2024/"}],
    "cds 2023": [{"title": "CDS 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-2023/"}],
    "cds 2022": [{"title": "CDS 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-2022/"}],
    "cds 2021": [{"title": "CDS 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-2021/"}],
    "cds 2020": [{"title": "CDS 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-2020/"}],
    "cds": [{"title": "CDS All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-question-papers/"}],
    
    # ═══════════════════════════════════════════════════════════
    # CBSE Class 10 - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "cbse class 10 2024": [
        {"title": "CBSE Class 10 2024 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2024/"},
        {"title": "CBSE 10th 2024 All Subjects", "url": "https://www.selfstudys.com/cbse/class-10th-question-paper/2024"},
    ],
    "cbse class 10 2023": [
        {"title": "CBSE Class 10 2023 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2023/"},
        {"title": "CBSE 10th 2023 All Subjects", "url": "https://www.selfstudys.com/cbse/class-10th-question-paper/2023"},
    ],
    "cbse class 10 2022": [
        {"title": "CBSE Class 10 2022 Term 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2022/"},
        {"title": "CBSE 10th 2022 All Subjects", "url": "https://www.selfstudys.com/cbse/class-10th-question-paper/2022"},
    ],
    "cbse class 10 2021": [
        {"title": "CBSE Class 10 2021 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2021/"},
        {"title": "CBSE 10th 2021 All Subjects", "url": "https://www.selfstudys.com/cbse/class-10th-question-paper/2021"},
    ],
    "cbse class 10 2020": [
        {"title": "CBSE Class 10 2020 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2020/"},
        {"title": "CBSE 10th 2020 All Subjects", "url": "https://www.selfstudys.com/cbse/class-10th-question-paper/2020"},
    ],
    "cbse class 10 2019": [
        {"title": "CBSE Class 10 2019 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2019/"},
    ],
    "cbse class 10 2018": [
        {"title": "CBSE Class 10 2018 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2018/"},
    ],
    "cbse class 10": [
        {"title": "CBSE Class 10 All Years - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-question-papers/"},
        {"title": "CBSE Official Sample Papers", "url": "https://cbseacademic.nic.in/SQP_CLASSXI.html"},
        {"title": "CBSE 10th All Years - SelfStudys", "url": "https://www.selfstudys.com/cbse/class-10th-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # CBSE Class 12 - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "cbse class 12 2024": [
        {"title": "CBSE Class 12 2024 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2024/"},
        {"title": "CBSE 12th 2024 All Subjects", "url": "https://www.selfstudys.com/cbse/class-12th-question-paper/2024"},
    ],
    "cbse class 12 2023": [
        {"title": "CBSE Class 12 2023 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2023/"},
        {"title": "CBSE 12th 2023 All Subjects", "url": "https://www.selfstudys.com/cbse/class-12th-question-paper/2023"},
    ],
    "cbse class 12 2022": [
        {"title": "CBSE Class 12 2022 Term 1 & 2 - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2022/"},
        {"title": "CBSE 12th 2022 All Subjects", "url": "https://www.selfstudys.com/cbse/class-12th-question-paper/2022"},
    ],
    "cbse class 12 2021": [
        {"title": "CBSE Class 12 2021 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2021/"},
        {"title": "CBSE 12th 2021 All Subjects", "url": "https://www.selfstudys.com/cbse/class-12th-question-paper/2021"},
    ],
    "cbse class 12 2020": [
        {"title": "CBSE Class 12 2020 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2020/"},
        {"title": "CBSE 12th 2020 All Subjects", "url": "https://www.selfstudys.com/cbse/class-12th-question-paper/2020"},
    ],
    "cbse class 12 2019": [
        {"title": "CBSE Class 12 2019 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2019/"},
    ],
    "cbse class 12 2018": [
        {"title": "CBSE Class 12 2018 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2018/"},
    ],
    "cbse class 12": [
        {"title": "CBSE Class 12 All Years - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-question-papers/"},
        {"title": "CBSE Official Sample Papers", "url": "https://cbseacademic.nic.in/SQP_CLASSXII.html"},
        {"title": "CBSE 12th All Years - SelfStudys", "url": "https://www.selfstudys.com/cbse/class-12th-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # ICSE / ISC
    # ═══════════════════════════════════════════════════════════
    "icse class 10": [
        {"title": "ICSE Class 10 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/icse-question-papers/"},
        {"title": "ICSE 10th Papers - SelfStudys", "url": "https://www.selfstudys.com/icse/class-10th-question-paper"},
    ],
    "isc class 12": [
        {"title": "ISC Class 12 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/isc-question-papers/"},
        {"title": "ISC 12th Papers - SelfStudys", "url": "https://www.selfstudys.com/isc/class-12th-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # NIOS / UP Board / Bihar Board
    # ═══════════════════════════════════════════════════════════
    "nios": [
        {"title": "NIOS Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nios-question-papers/"},
        {"title": "NIOS Official Papers", "url": "https://www.nios.ac.in/online-services/question-papers.aspx"},
    ],
    "up board": [
        {"title": "UP Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/up-board-question-papers/"},
        {"title": "UP Board 10th & 12th Papers", "url": "https://www.selfstudys.com/up-board"},
    ],
    "bihar board": [
        {"title": "Bihar Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/bihar-board-question-papers/"},
        {"title": "Bihar Board 10th & 12th Papers", "url": "https://www.selfstudys.com/bihar-board"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # CAT - All Years 2018-2024
    # ═══════════════════════════════════════════════════════════
    "cat 2024": [
        {"title": "CAT 2024 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2024/"},
        {"title": "CAT 2024 Papers PDF", "url": "https://www.selfstudys.com/cat-2024-question-paper"},
    ],
    "cat 2023": [
        {"title": "CAT 2023 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2023/"},
        {"title": "CAT 2023 Papers PDF", "url": "https://www.selfstudys.com/cat-2023-question-paper"},
    ],
    "cat 2022": [
        {"title": "CAT 2022 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2022/"},
        {"title": "CAT 2022 Papers PDF", "url": "https://www.selfstudys.com/cat-2022-question-paper"},
    ],
    "cat 2021": [
        {"title": "CAT 2021 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2021/"},
        {"title": "CAT 2021 Papers PDF", "url": "https://www.selfstudys.com/cat-2021-question-paper"},
    ],
    "cat 2020": [
        {"title": "CAT 2020 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2020/"},
    ],
    "cat 2019": [
        {"title": "CAT 2019 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2019/"},
    ],
    "cat 2018": [
        {"title": "CAT 2018 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2018/"},
    ],
    "cat": [
        {"title": "CAT All Years Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cat-question-papers/"},
        {"title": "CAT Previous Papers - Careers360", "url": "https://bschool.careers360.com/articles/cat-previous-year-question-papers"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # CLAT - All Years
    # ═══════════════════════════════════════════════════════════
    "clat 2024": [
        {"title": "CLAT 2024 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/clat-2024/"},
        {"title": "CLAT 2024 Papers PDF", "url": "https://www.selfstudys.com/clat-2024-question-paper"},
    ],
    "clat 2023": [
        {"title": "CLAT 2023 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/clat-2023/"},
        {"title": "CLAT 2023 Papers PDF", "url": "https://www.selfstudys.com/clat-2023-question-paper"},
    ],
    "clat 2022": [{"title": "CLAT 2022 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/clat-2022/"}],
    "clat 2021": [{"title": "CLAT 2021 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/clat-2021/"}],
    "clat 2020": [{"title": "CLAT 2020 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/clat-2020/"}],
    "clat": [
        {"title": "CLAT All Years Papers - AglaSem", "url": "https://schools.aglasem.com/tag/clat-question-papers/"},
        {"title": "CLAT Papers PDF", "url": "https://www.selfstudys.com/clat-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # CUET - All Years
    # ═══════════════════════════════════════════════════════════
    "cuet 2024": [
        {"title": "CUET 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cuet-2024/"},
        {"title": "CUET 2024 Papers PDF", "url": "https://www.selfstudys.com/cuet-ug-2024-question-paper"},
    ],
    "cuet 2023": [
        {"title": "CUET 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cuet-2023/"},
        {"title": "CUET 2023 Papers PDF", "url": "https://www.selfstudys.com/cuet-ug-2023-question-paper"},
    ],
    "cuet 2022": [{"title": "CUET 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cuet-2022/"}],
    "cuet": [
        {"title": "CUET All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cuet-question-papers/"},
        {"title": "CUET Papers PDF", "url": "https://www.selfstudys.com/cuet-ug-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # NIFT
    # ═══════════════════════════════════════════════════════════
    "nift": [
        {"title": "NIFT Entrance Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nift-question-papers/"},
        {"title": "NIFT Papers PDF", "url": "https://www.selfstudys.com/nift-question-paper"},
    ],
    
    # ═══════════════════════════════════════════════════════════
    # DU LLB
    # ═══════════════════════════════════════════════════════════
    "du llb": [
        {"title": "DU LLB Entrance Papers - AglaSem", "url": "https://schools.aglasem.com/tag/du-llb-question-papers/"},
        {"title": "DU LLB Papers PDF", "url": "https://www.selfstudys.com/du-llb-question-paper"},
    ],
}

def get_static_results(query_text: str) -> List[dict]:
    """Super-smart matching: Direct hits, and keyword intersections."""
    q_clean = query_text.lower().replace("main ", "mains ").strip()
    q_words = set(q_clean.split())
    
    # 1. Exact direct check
    if q_clean in STATIC_DB: return STATIC_DB[q_clean]
    
    # 2. Look for best intersection
    best_results = []
    max_score = 0
    for key, data in STATIC_DB.items():
        key_words = set(key.split())
        intersection = key_words.intersection(q_words)
        score = len(intersection)
        if key_words.issubset(q_words): score += 10 # Perfect meaning
        
        if score > max_score and score >= 2:
            max_score = score
            best_results = data
            
    return best_results

async def search_papers(query_text: str, limit: int = 6) -> Tuple[List[dict], str]:
    """Multi-layer search with tracking report."""
    results = []
    seen_urls = set()
    stats = []
    
    def add(items, source_id):
        count = 0
        for r in items:
            url = r['url'].split('#')[0]
            if url not in seen_urls:
                results.append(r)
                seen_urls.add(url)
                count += 1
        if count > 0: stats.append(f"✅ {source_id}({count})")
        else: stats.append(f"❌ {source_id}")

    # L1: Ecosia
    try: add(await search_ecosia(query_text, limit=4), "Eco")
    except: stats.append("⚠️ EcoFail")
    
    # L2: Bing
    if len(results) < 3:
        try: add(await search_bing(query_text, limit=4), "Bin")
        except: stats.append("⚠️ BinFail")
        
    # L3: DDG HTML
    if len(results) < 3:
        try: add(await search_ddg_html(query_text, limit=4), "Ddg")
        except: stats.append("⚠️ DdgFail")

    # L4: Google
    if len(results) < 2:
        try: add(await search_google(query_text, limit=4), "Ggl")
        except: stats.append("⚠️ GglFail")

    # L5: DDGS Library (Aggressive Fallback)
    if len(results) < 1:
        try:
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(None, lambda: list(DDGS().text(f"{query_text} pdf", max_results=5)))
            add([{"title": r.get('title','Result'), "url": r.get('href','')} for r in raw], "Lib")
        except: stats.append("⚠️ LibFail")

    return results[:limit], " | ".join(stats)


async def download_and_send_pdf(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE, depth: int = 0, status_msg=None):
    """Enhanced PDF download with site-specific scrapers and better heuristics."""
    if depth > 5: return "failed"
    try:
        # ─── SITE-SPECIFIC TRANSFORMATIONS ───
        original_url = url
        
        # SelfStudys Transformation
        if "selfstudys.com" in url:
            if "/pdf-viewer/" in url:
                url = url.replace("/pdf-viewer/", "/download-pdf/").replace(".php", "")
        
        # Google Drive Download link
        if ("drive.google.com" in url or "docs.google.com" in url) and "/d/" in url:
            try:
                file_id = url.split("/d/")[1].split("/")[0].split("?")[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
            except: pass

        # ─── DOWNLOAD ATTEMPT ───
        if status_msg and depth <= 1:
            try:
                domain = urllib.parse.urlparse(url).netloc[:30]
                indicator = "🚀 Exploring..." if depth > 0 else "⚡ Connecting..."
                await status_msg.edit_text(f"**{indicator}**\n📍 `{domain}`", parse_mode="Markdown")
            except: pass

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.google.com/"
        }
        
        async with primp.AsyncClient(impersonate="chrome_123", follow_redirects=True, verify=False) as client:
            response = await client.get(url, timeout=35, headers=headers)
            
            if response.status_code not in [200, 206]:
                return "failed"
                
            ctype = response.headers.get("Content-Type", "").lower()
            content = response.content
            
            # 1. DIRECT PDF DETECTION
            is_pdf = content.startswith(b"%PDF-") or "pdf" in ctype or (len(content) > 1024 and b"%PDF-" in content[:1024])
            
            if is_pdf:
                if len(content) > 48 * 1024 * 1024: return "large"
                
                # Filename logic
                fname = "Exam_Paper.pdf"
                for key in ["jee", "neet", "gate", "upsc", "ssc", "board", "cat", "nda", "cds", "cbse"]:
                    if key in original_url.lower():
                         fname = f"{key.upper()}_Paper.pdf"
                         break
                
                msg = update.callback_query.message if update.callback_query else update.message
                await msg.reply_document(
                    document=io.BytesIO(content),
                    filename=fname,
                    caption=f"✅ **Direct Download Success!**\n\n📄 {fname}\n\n_Note: This PDF was extracted directly from the source._"
                )
                return "sent"

            # 2. HTML PAGE - DEEP EXTRACTION
            if "html" in ctype or "text" in ctype or len(content) < 5000:
                soup = BeautifulSoup(response.text, 'html.parser')
                candidates = []
                
                # Check for buttons/links with specific download keywords
                for a in soup.find_all(['a', 'button'], href=True if soup.name == 'a' else False):
                    href = a.get('href') if a.name == 'a' else None
                    if not href: continue
                    
                    text = a.get_text(strip=True).lower()
                    full_href = urllib.parse.urljoin(url, href)
                    
                    if full_href == url or full_href.startswith('javascript') or full_href.startswith('#'):
                        continue
                    
                    score = 0
                    if full_href.lower().endswith('.pdf'): score += 100
                    if "download pdf" in text: score += 90
                    if "download" in text: score += 70
                    if "pdf" in text: score += 50
                    if "question paper" in text: score += 40
                    
                    # Site specific weight
                    if "selfstudys.com" in full_href and "download" in full_href: score += 30
                    if "aglasem.com" in full_href and "pdf" in full_href: score += 30
                    
                    if score > 35:
                        candidates.append((score, full_href))
                
                # Look for iframes (Google Drive viewers, etc)
                for iframe in soup.find_all('iframe', src=True):
                    src = iframe.get('src')
                    full_src = urllib.parse.urljoin(url, src)
                    if "pdf" in full_src.lower() or "drive.google.com" in full_src:
                        candidates.append((85, full_src))

                # Sort and try recursively
                candidates.sort(key=lambda x: x[0], reverse=True)
                seen_cands = {url, original_url}
                for _, cand in candidates[:5]:
                    if cand in seen_cands: continue
                    seen_cands.add(cand)
                    
                    res = await download_and_send_pdf(cand, update, context, depth + 1, status_msg)
                    if res == "sent": return "sent"
                    if res == "large": return "large"

    except Exception as e:
        logger.error(f"Download handle error for {url}: {e}")
    
    return "failed"



async def year_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Result renderer — uses Static DB directly for guaranteed results."""
    query = update.callback_query
    await query.answer("Fetching results...")
    parts = query.data.split("|")
    cat_name = parts[1]
    exam_name = parts[2]
    year = parts[3]

    await query.edit_message_text(f"⚡ **Searching {exam_name} ({year})...**", parse_mode="Markdown")
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

    # ── DIRECT STATIC DB LOOKUP (exam_name + year, no search needed) ──
    # Map exam button names to their static DB key prefixes
    EXAM_TO_KEY = {
        "JEE Mains":      "jee mains",
        "JEE Advanced":   "jee advanced",
        "GATE":           "gate",
        "BITSAT":         "bitsat",
        "WBJEE":          "wbjee",
        "WBJEE JELET":    "wbjee jelet",
        "WBJEE JENPAS":   "wbjee jenpas",
        "MHT CET":        "mht cet",
        "NEET UG":        "neet ug",
        "NEET PG":        "neet pg",
        "AIIMS":          "aiims",
        "JIPMER":         "jipmer",
        "UPSC CSE (IAS)": "upsc cse",
        "SSC CGL":        "ssc cgl",
        "SSC CHSL":       "ssc chsl",
        "IBPS PO":        "ibps po",
        "SBI PO":         "sbi po",
        "RRB NTPC":       "rrb ntpc",
        "NDA/CDS":        "nda",
        "CBSE Class 10":  "cbse class 10",
        "CBSE Class 12":  "cbse class 12",
        "ICSE Class 10":  "icse class 10",
        "ISC Class 12":   "isc class 12",
        "NIOS":           "nios",
        "UP Board":       "up board",
        "Bihar Board":    "bihar board",
        "CAT":            "cat",
        "CLAT":           "clat",
        "NIFT":           "nift",
        "CUET":           "cuet",
        "DU LLB":         "du llb",
    }

    results = []
    seen_urls = set()

    def add(title, url):
        if url and url not in seen_urls:
            results.append({"title": title[:80], "url": url})
            seen_urls.add(url)

    base_key = EXAM_TO_KEY.get(exam_name, exam_name.lower())
    year_key = f"{base_key} {year}".lower().strip()
    
    # 1. Try Specific year match first
    results_static = STATIC_DB.get(year_key, [])
    if not results_static:
        # 2. Try general exam match
        results_static = STATIC_DB.get(base_key, [])
    
    for res in results_static:
        add(res['title'], res['url'])

    # 3. IF NO STATIC DB MATCH, OR FOR "OLDER" PAPERS, FALLBACK TO SEARCH
    search_stats = ""
    if not results or year == "Older" or len(results) < 2:
        final_query = f"{exam_name} {year if year != 'Older' else ''} question paper pdf".strip()
        live_res, search_stats = await search_papers(final_query, limit=5-len(results))
        for r in live_res: add(r['title'], r['url'])

    footer = f"\n\n---\n🤖 **ExamBot {BOT_VERSION}**"

    if not results:
        report = f"❌ **No results found for {exam_name} ({year}).**"
        if search_stats: report += f"\n\n🔎 Diagnostics: `{search_stats}`"
        await query.edit_message_text(report + footer, parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"exam|{cat_name}|{exam_name}")]]))
        return

    # ────── ONE-CLICK AUTOMATED DOWNLOAD PROGRESSION ──────
    context.user_data['last_results'] = results
    diag_info = f"\n📦 `Sources: {search_stats}`" if search_stats else ""
    
    wait_msg = await query.edit_message_text(
        f"🎯 **Year: {year} | Exam: {exam_name}**\n\n"
        f"🚀 **Starting One-Click Auto-Download...**\n"
        f"Hunting for the best match in our database...{diag_info}",
        parse_mode="Markdown"
    )

    # ─── AUTO-TRY MULTIPLE RESULTS ───
    status = "failed"
    best_results = results[:3] 
    for i, res in enumerate(best_results):
        status = await download_and_send_pdf(res['url'], update, context, 0, wait_msg)
        if status == "sent": break
    
    if status == "sent":
        response = f"✅ **PDF Sent!**\n\nSuccessfully delivered the best match for **{exam_name} ({year})**."
    else:
        response = f"📚 **Results for {exam_name} ({year}):**\n\n⚠️ *Auto-download failed. Try manually:* \n"

    keyboard = []
    for i, res in enumerate(results):
        if not status == "sent": response += f"📄 {i+1}. **{res['title']}**\n"
        keyboard.append([InlineKeyboardButton(f"📥 Download V{i+1}", callback_data=f"dl_{i}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"exam|{cat_name}|{exam_name}")])
    
    try: await wait_msg.edit_text(response + footer, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except: pass

async def direct_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explains how to use direct search when the button is clicked."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🔍 **How to use Direct Search:**\n\n"
        "Just type the **Exam Name** and **Year** directly in the chat.\n"
        "Example: `JEE Mains 2022` or `CBSE Class 12 Physics 2023`.\n\n"
        "I will find the best PDF links for you instantly!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smart direct search: Ignores greetings and filters for relevant exam queries."""
    query_text = update.message.text.strip()
    query_lower = query_text.lower()
    
    # 1. Filter out common greetings and random junk
    greetings = ["hi", "hello", "hey", "namaste", "gh", "hj", "ok", "thanks", "thank you", "bye"]
    if query_lower in greetings or len(query_text) < 3:
        await update.message.reply_text(
            "👋 **Hi! Please use the /start menu to browse exams.**\n\n"
            "If you want to search directly, type something specific like `JEE 2022` or `UPSC Ethics Paper`."
        )
        return

    # 2. Heuristic: Only search if it looks like an exam/year query
    # Look for a 4-digit year or common exam keywords
    words = query_lower.split()
    exam_keywords = ["jee", "neet", "upsc", "ssc", "board", "class", "10th", "12th", "paper", "exam", "solved", "gate", "cat", "clat", "nda", "cds"]
    has_year = any(word.isdigit() and len(word) == 4 for word in words)
    has_keyword = any(kw in query_lower for kw in exam_keywords)

    if not (has_year or has_keyword or len(words) >= 2):
        # If it doesn't look like an exam query, don't waste search time
        await update.message.reply_text("🤔 I'm not sure which exam you're looking for. Please type the **Exam Name + Year** (e.g., `JEE 2023`).")
        return

    # 3. Proceed with search for relevant queries
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    status_msg = await update.message.reply_text(f"🔍 **Searching for:** *{query_text}*", parse_mode="Markdown")
    
    # ─── A: CHECK STATIC DB FIRST ───
    static_results = get_static_results(query_text)
    
    # ─── B: DO LIVE SEARCH ───
    live_results, search_stats = await search_papers(query_text, limit=6)
    
    # Merge results
    results = []
    seen_urls = set()
    for res in static_results + live_results:
        if res['url'] not in seen_urls:
            results.append(res)
            seen_urls.add(res['url'])

    footer = f"\n\n---\n🤖 **ExamBot {BOT_VERSION}**"

    if not results:
        report = f"❌ **No results found.**\n\n🔎 Diagnostics: `{search_stats}`" if search_stats else "❌ **No results found.**"
        await status_msg.edit_text(report + footer, parse_mode="Markdown")
        return

    # ─── AUTOMATED DOWNLOAD FROM SEARCH ───
    wait_msg = status_msg
    diag_info = f"\n📦 `Sources: {search_stats}`" if search_stats else ""
    try: await wait_msg.edit_text(f"🎯 **Found results for: {query_text}**\n🚀 **Attempting Auto-Download...**{diag_info}", parse_mode="Markdown")
    except: pass
    
    status = "failed"
    best_results = results[:2] 
    for i, res in enumerate(best_results):
        status = await download_and_send_pdf(res['url'], update, context, 0, wait_msg)
        if status == "sent": break

    if status == "sent":
        response = f"✅ **PDF Sent!**\n\nI found the best match for **{query_text}**.\nIf this isn't correct, check variants below:"
    else:
        response = f"📚 **Search Results for: {query_text}**\n\n⚠️ *Auto-download failed. Try manually:* \n"

    keyboard = []
    for i, res in enumerate(results):
        if not status == "sent": response += f"📄 {i+1}. **{res['title']}**\n"
        keyboard.append([InlineKeyboardButton(f"📥 Download V{i+1}", callback_data=f"dl_{i}")])
    
    context.user_data['last_results'] = results
    try: await wait_msg.edit_text(response + footer, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except: pass

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refined download handler with informative errors."""
    query = update.callback_query
    await query.answer("Preparing download...")
    
    try:
        parts = query.data.split("_")
        if len(parts) < 2: return
        idx = int(parts[1])
        
        results = context.user_data.get('last_results', [])
        
        if not results:
            await query.message.reply_text("❌ **Session Expired!**\n\nPlease search for the exam again. Results are only kept for a short time for security.")
            return

        if idx < len(results):
            url = results[idx]['url']
            title = results[idx]['title']
            
            # Show progress
            await context.bot.send_chat_action(chat_id=query.message.chat_id, action="upload_document")
            wait_msg = await query.message.reply_text(f"⚡ **Searching for direct PDF for:**\n*{title}*\n\n*This may take a few seconds...*", parse_mode="Markdown")
            
            # Run extraction
            status = await download_and_send_pdf(url, update, context, 0, wait_msg)
            
            # Cleanup wait message
            try: await wait_msg.delete()
            except: pass
            
            if status == "large":
                await query.message.reply_text(
                    f"📂 **File is too large!**\n\n"
                    f"The PDF is larger than 50MB, which is the limit for Telegram bots.\n"
                    f"Please download it manually using the link below:\n\n"
                    f"🔗 **[Download Large Paper]({url})**",
                    parse_mode="Markdown"
                )
            elif status == "failed":
                await query.message.reply_text(
                    f"⚠️ **Note:** Direct PDF delivery failed for this link.\n\n"
                    f"This site might have bot protection or requires manual captcha.\n\n"
                    f"🔗 **[Click here to open the paper in browser]({url})**",
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
        else:
            await query.message.reply_text("❌ **Invalid selection.** Please try searching again.")
            
    except Exception as e:
        logger.error(f"Error in download_callback: {e}")
        await query.message.reply_text("❌ **An unexpected error occurred.** Please try again /start.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "📖 **How to Use:**\n\n"
        "1. Use `/start` to browse categorized exams.\n"
        "2. Alternatively, type any exam name directly (e.g., 'JEE 2023 Physics').\n"
        "3. Click the **Direct Download** button to receive the PDF file instantly."
    )
    await update.message.reply_text(help_msg, parse_mode="Markdown")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tests all 5 search engines and reports results directly in chat."""
    msg = await update.message.reply_text("🔬 **Running 5-Layer Search Diagnostics...**", parse_mode="Markdown")
    report = ["🔬 **Multi-Layer Search Report**\n"]
    test_query = "JEE Mains 2024 paper"
    report.append(f"📋 Query: `{test_query}`\n")

    # 1. Ecosia
    try:
        res = await search_ecosia(test_query, limit=3)
        report.append(f"{'✅' if res else '❌'} Layer 1 (Ecosia): {len(res)} results")
    except Exception as e: report.append(f"❌ Ecosia Error: {str(e)[:40]}")

    # 2. Bing
    try:
        res = await search_bing(test_query, limit=3)
        report.append(f"{'✅' if res else '❌'} Layer 2 (Bing): {len(res)} results")
    except Exception as e: report.append(f"❌ Bing Error: {str(e)[:40]}")

    # 3. DDG HTML
    try:
        res = await search_ddg_html(test_query, limit=3)
        report.append(f"{'✅' if res else '❌'} Layer 3 (DDG): {len(res)} results")
    except Exception as e: report.append(f"❌ DDG Error: {str(e)[:40]}")

    # 4. Google
    try:
        res = await search_google(test_query, limit=3)
        report.append(f"{'✅' if res else '❌'} Layer 4 (Google): {len(res)} results")
    except Exception as e: report.append(f"❌ Google Error: {str(e)[:40]}")

    # 5. DDGS
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: list(DDGS().text(test_query, max_results=3)))
        report.append(f"{'✅' if res else '❌'} Layer 5 (DDGS): {len(res)} results")
    except Exception as e: report.append(f"❌ DDGS Error: {str(e)[:40]}")

    # 6. Static DB
    try:
        res = get_static_results("jee mains 2024")
        report.append(f"{'✅' if res else '❌'} Static DB Check: {len(res)} items")
    except Exception as e: report.append(f"❌ Static DB Error: {str(e)[:40]}")

    await msg.edit_text("\n".join(report), parse_mode="Markdown")

def main():
    logger.info("🚀 Starting Bot Application v11.0 LIVE Premium (Cloud Ready)...")
    
    # 🌟 CLOUD HEALTH-CHECK HACK (CRITICAL)
    # Hugging Face Spaces look for port 7860 to show the bot as "Running".
    PORT = int(os.environ.get("PORT", "7860"))
    if not BOT_TOKEN:
        logger.error("❌ ERROR: TELEGRAM_BOT_TOKEN is missing! Please set it in Settings -> Secrets.")
        raise ValueError("TELEGRAM_BOT_TOKEN is not set.")
    
    def run_cloud_keep_alive():
        from http.server import HTTPServer, BaseHTTPRequestHandler
        class HealthCheck(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Bot is online (Cloud Health Check OK)")
            
            def log_message(self, format, *args):
                pass 

        def ping_self():
            import time
            import requests
            # Derive URL from SPACE_ID on Hugging Face
            space_id = os.environ.get("SPACE_ID")
            default_url = f"https://{space_id.replace('/', '-')}.hf.space" if space_id else "https://ayush447-exam-assistant-bot.hf.space"
            url = os.environ.get("SELF_URL") or default_url
            
            logger.info(f"📡 Self-ping started for: {url}")
            time.sleep(30) # Initial delay for server start
            while True:
                try:
                    # Just hit the health endpoint
                    requests.get(url, timeout=10)
                    logger.info("📡 Self-ping: OK")
                except Exception as e:
                    logger.warning(f"📡 Self-ping failed: {e}")
                time.sleep(600) # Ping every 10 min

        threading.Thread(target=ping_self, daemon=True).start()

        try:
            httpd = HTTPServer(('0.0.0.0', PORT), HealthCheck)
            logger.info(f"✅ Cloud Health Server listening on port {PORT}")
            httpd.serve_forever()
        except Exception as e:
            logger.error(f"❌ Health-Check Server error: {e}")

    # Launch health check in background thread
    threading.Thread(target=run_cloud_keep_alive, daemon=True).start()

    # Build bot application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CallbackQueryHandler(start, pattern="^back_cats$"))
    application.add_handler(CallbackQueryHandler(direct_search_callback, pattern="^direct_search$"))
    application.add_handler(CallbackQueryHandler(category_handler, pattern="^cat"))
    application.add_handler(CallbackQueryHandler(exam_handler, pattern="^exam"))
    application.add_handler(CallbackQueryHandler(year_handler, pattern="^year"))
    application.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # START THE BOT
    logger.info(f"📡 PRODUCTION: Using Stable Polling (Health server on port {PORT})")
    application.run_polling()

if __name__ == "__main__":
    main()

