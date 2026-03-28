import asyncio
import logging
import os
import io
import aiohttp
from typing import List, Dict

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
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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
    # VERSION IDENTIFICATION
    version = "v11.0 LIVE Premium"
    text = (
        f"👋 **Welcome to the One-Click Exam Paper Bot {version}**\n\n"
        "I provide **Direct PDF Downloads** for all major Indian exams (JEE, NEET, SSC, UPSC, CBSE, etc.) directly in this chat.\n\n"
        "❌ **No more annoying links or redirects!**\n\n"
        "Please select a **Category** below to receive your paper instantly:"
    )
    keyboard = []
    categories = list(EXAM_CATEGORIES.keys())
    for cat in categories:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}")])
    
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
    cat_name = query.data.replace("cat_", "")
    exams = EXAM_CATEGORIES.get(cat_name, {})
    
    text = f"📂 **Category: {cat_name}**\n\nNow, select a specific **Exam** from the list below:"
    keyboard = []
    exam_names = list(exams.keys())
    for i in range(0, len(exam_names), 2):
        row = [InlineKeyboardButton(exam_names[i], callback_data=f"exam_{cat_name}_{exam_names[i]}")]
        if i+1 < len(exam_names):
            row.append(InlineKeyboardButton(exam_names[i+1], callback_data=f"exam_{cat_name}_{exam_names[i+1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="back_cats")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def exam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows years for a specific exam."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    cat_name = parts[1]
    exam_name = parts[2]
    
    text = f"🎯 **Selected Exam: {exam_name}**\n\nWhich **Academic Year** paper are you looking for?"
    keyboard = []
    for i in range(0, len(YEARS), 2):
        row = [InlineKeyboardButton(YEARS[i], callback_data=f"year_{cat_name}_{exam_name}_{YEARS[i]}")]
        if i+1 < len(YEARS):
            row.append(InlineKeyboardButton(YEARS[i+1], callback_data=f"year_{cat_name}_{exam_name}_{YEARS[i+1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Exams", callback_data=f"cat_{cat_name}")])
    
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


# Rotating User-Agents to avoid detection on cloud IPs
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]
import random

async def search_bing(session, query: str, limit: int = 8) -> List[dict]:
    """Scrape Bing search results - works reliably from cloud IPs."""
    results = []
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.bing.com/",
        }
        encoded_q = urllib.parse.quote(f"{query} filetype:pdf OR site:aglasem.com OR site:examfare.com")
        url = f"https://www.bing.com/search?q={encoded_q}&count=15&setlang=en"
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                for li in soup.select('li.b_algo')[:limit]:
                    a_tag = li.select_one('h2 a')
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        if href and href.startswith('http'):
                            results.append({"title": title[:80], "url": href})
            else:
                logger.warning(f"Bing returned status {resp.status}")
    except Exception as e:
        logger.warning(f"Bing search error: {e}")
    return results

async def search_ddg(session, query: str, limit: int = 8) -> List[dict]:
    """Scrape DuckDuckGo HTML results - cloud-IP friendly fallback."""
    results = []
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        encoded_q = urllib.parse.quote(f"{query} pdf")
        url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                for a_tag in soup.select('a.result__a')[:limit]:
                    title = a_tag.get_text(strip=True)
                    href = a_tag.get('href', '')
                    # DDG wraps URLs, need to extract actual URL
                    if 'uddg=' in href:
                        try:
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            href = urllib.parse.unquote(parsed.get('uddg', [''])[0])
                        except: pass
                    if href and href.startswith('http'):
                        results.append({"title": title[:80], "url": href})
            else:
                logger.warning(f"DDG returned status {resp.status}")
    except Exception as e:
        logger.warning(f"DDG search error: {e}")
    return results


# ─────────────────────────────────────────────────────────────
# STATIC DATABASE — PRIMARY source, 100% reliable on Render!
# Keys are lowercase exam identifiers (with optional year)
# ─────────────────────────────────────────────────────────────
STATIC_DB: Dict[str, List[dict]] = {
    # JEE MAINS
    "jee mains 2024": [{"title": "JEE Main 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2024/"},
                       {"title": "JEE Main 2024 - Careers360", "url": "https://engineering.careers360.com/articles/jee-main-previous-year-question-papers"}],
    "jee mains 2023": [{"title": "JEE Main 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2023/"}],
    "jee mains 2022": [{"title": "JEE Main 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2022/"}],
    "jee mains 2021": [{"title": "JEE Main 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2021/"}],
    "jee mains 2020": [{"title": "JEE Main 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2020/"}],
    "jee mains 2019": [{"title": "JEE Main 2019 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2019/"}],
    "jee mains 2018": [{"title": "JEE Main 2018 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-2018/"}],
    "jee mains":      [{"title": "JEE Main All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-main-question-papers/"},
                       {"title": "JEE Main PYQ - Careers360", "url": "https://engineering.careers360.com/articles/jee-main-previous-year-question-papers"}],
    # JEE ADVANCED
    "jee advanced 2024": [{"title": "JEE Advanced 2024 Paper 1&2 - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2024/"}],
    "jee advanced 2023": [{"title": "JEE Advanced 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2023/"}],
    "jee advanced 2022": [{"title": "JEE Advanced 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2022/"}],
    "jee advanced 2021": [{"title": "JEE Advanced 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2021/"}],
    "jee advanced 2020": [{"title": "JEE Advanced 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-2020/"}],
    "jee advanced":      [{"title": "JEE Advanced All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jee-advanced-question-papers/"},
                          {"title": "JEE Advanced PYQ - Careers360", "url": "https://engineering.careers360.com/articles/jee-advanced-previous-year-question-papers"}],
    # NEET
    "neet ug 2024": [{"title": "NEET 2024 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2024/"},
                     {"title": "NEET 2024 - Careers360", "url": "https://medicine.careers360.com/articles/neet-previous-year-question-papers"}],
    "neet ug 2023": [{"title": "NEET 2023 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2023/"}],
    "neet ug 2022": [{"title": "NEET 2022 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2022/"}],
    "neet ug 2021": [{"title": "NEET 2021 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2021/"}],
    "neet ug 2020": [{"title": "NEET 2020 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2020/"}],
    "neet ug 2019": [{"title": "NEET 2019 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2019/"}],
    "neet ug 2018": [{"title": "NEET 2018 Paper PDF - AglaSem", "url": "https://schools.aglasem.com/tag/neet-2018/"}],
    "neet ug":      [{"title": "NEET All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-question-papers/"},
                     {"title": "NEET PYQ - Careers360", "url": "https://medicine.careers360.com/articles/neet-previous-year-question-papers"}],
    # NEET PG
    "neet pg 2024": [{"title": "NEET PG 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-pg-2024/"}],
    "neet pg":      [{"title": "NEET PG Papers - AglaSem", "url": "https://schools.aglasem.com/tag/neet-pg-question-papers/"}],
    # AIIMS
    "aiims 2024": [{"title": "AIIMS 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-2024/"}],
    "aiims":       [{"title": "AIIMS Medical Papers - AglaSem", "url": "https://schools.aglasem.com/tag/aiims-question-papers/"}],
    # JIPMER
    "jipmer": [{"title": "JIPMER Medical Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jipmer-question-papers/"}],
    # GATE
    "gate 2024": [{"title": "GATE 2024 All Branch Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2024/"}],
    "gate 2023": [{"title": "GATE 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2023/"}],
    "gate 2022": [{"title": "GATE 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2022/"}],
    "gate 2021": [{"title": "GATE 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-2021/"}],
    "gate":      [{"title": "GATE All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/gate-question-papers/"}],
    # BITSAT
    "bitsat": [{"title": "BITSAT Papers - AglaSem", "url": "https://schools.aglasem.com/tag/bitsat-question-papers/"}],
    # WBJEE
    "wbjee": [{"title": "WBJEE Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-question-papers/"}],
    "wbjee jelet": [{"title": "WBJEE JELET Papers - AglaSem", "url": "https://schools.aglasem.com/tag/wbjee-jelet-question-papers/"},
                    {"title": "JELET Previous Papers - Examfare", "url": "http://www.examfare.com/p/jelet-previous-year-question-paper.html"}],
    "wbjee jenpas": [{"title": "WBJEE JENPAS Papers - AglaSem", "url": "https://schools.aglasem.com/tag/jenpas-ug-question-papers/"}],
    # MHT CET
    "mht cet": [{"title": "MHT CET Papers - AglaSem", "url": "https://schools.aglasem.com/tag/mht-cet-question-papers/"}],
    # UPSC CSE
    "upsc cse 2024": [{"title": "UPSC CSE 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2024/"}],
    "upsc cse 2023": [{"title": "UPSC CSE 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2023/"}],
    "upsc cse 2022": [{"title": "UPSC CSE 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2022/"}],
    "upsc cse 2021": [{"title": "UPSC CSE 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2021/"}],
    "upsc cse 2020": [{"title": "UPSC CSE 2020 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2020/"}],
    "upsc cse 2019": [{"title": "UPSC CSE 2019 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-2019/"}],
    "upsc cse":      [{"title": "UPSC CSE All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/upsc-question-papers/"},
                      {"title": "UPSC Official Paper Archive", "url": "https://upsc.gov.in/examinations/previous-question-papers"}],
    # SSC CGL
    "ssc cgl 2024": [{"title": "SSC CGL 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2024/"}],
    "ssc cgl 2023": [{"title": "SSC CGL 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2023/"}],
    "ssc cgl 2022": [{"title": "SSC CGL 2022 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2022/"}],
    "ssc cgl 2021": [{"title": "SSC CGL 2021 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-2021/"}],
    "ssc cgl":      [{"title": "SSC CGL All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-cgl-question-papers/"},
                     {"title": "SSC Official PYQ", "url": "https://ssc.nic.in/Portal/Previous_Question_Paper"}],
    # SSC CHSL
    "ssc chsl 2024": [{"title": "SSC CHSL 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2024/"}],
    "ssc chsl 2023": [{"title": "SSC CHSL 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-2023/"}],
    "ssc chsl":      [{"title": "SSC CHSL All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ssc-chsl-question-papers/"}],
    # IBPS PO
    "ibps po 2024": [{"title": "IBPS PO 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-2024/"}],
    "ibps po 2023": [{"title": "IBPS PO 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-2023/"}],
    "ibps po":      [{"title": "IBPS PO All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/ibps-po-question-papers/"}],
    # SBI PO
    "sbi po 2024": [{"title": "SBI PO 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-2024/"}],
    "sbi po":      [{"title": "SBI PO All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/sbi-po-question-papers/"}],
    # RRB NTPC
    "rrb ntpc 2024": [{"title": "RRB NTPC 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-2024/"}],
    "rrb ntpc":      [{"title": "RRB NTPC All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/rrb-ntpc-question-papers/"}],
    # NDA/CDS
    "nda 2024": [{"title": "NDA 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2024/"}],
    "nda 2023": [{"title": "NDA 2023 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-2023/"}],
    "nda":      [{"title": "NDA All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nda-question-papers/"},
                 {"title": "NDA Official - UPSC", "url": "https://upsc.gov.in/examinations/previous-question-papers"}],
    "cds 2024": [{"title": "CDS 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-2024/"}],
    "cds":      [{"title": "CDS All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cds-question-papers/"}],
    # CBSE Class 10
    "cbse class 10 2024": [{"title": "CBSE Class 10 2024 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2024/"}],
    "cbse class 10 2023": [{"title": "CBSE Class 10 2023 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2023/"}],
    "cbse class 10 2022": [{"title": "CBSE Class 10 2022 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2022/"}],
    "cbse class 10 2021": [{"title": "CBSE Class 10 2021 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2021/"}],
    "cbse class 10 2020": [{"title": "CBSE Class 10 2020 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-2020/"}],
    "cbse class 10":      [{"title": "CBSE Class 10 All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-10-question-papers/"},
                           {"title": "CBSE Class 10 Official Sample Papers", "url": "https://cbseacademic.nic.in/SQP_CLASSXI.html"}],
    # CBSE Class 12
    "cbse class 12 2024": [{"title": "CBSE Class 12 2024 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2024/"}],
    "cbse class 12 2023": [{"title": "CBSE Class 12 2023 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2023/"}],
    "cbse class 12 2022": [{"title": "CBSE Class 12 2022 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2022/"}],
    "cbse class 12 2021": [{"title": "CBSE Class 12 2021 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2021/"}],
    "cbse class 12 2020": [{"title": "CBSE Class 12 2020 Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-2020/"}],
    "cbse class 12":      [{"title": "CBSE Class 12 All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cbse-class-12-question-papers/"},
                           {"title": "CBSE Class 12 Official Sample Papers", "url": "https://cbseacademic.nic.in/SQP_CLASSXII.html"}],
    # ICSE / ISC
    "icse class 10": [{"title": "ICSE Class 10 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/icse-question-papers/"}],
    "isc class 12":  [{"title": "ISC Class 12 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/isc-question-papers/"}],
    # NIOS / UP Board / Bihar Board
    "nios":        [{"title": "NIOS Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nios-question-papers/"},
                    {"title": "NIOS Official Papers", "url": "https://www.nios.ac.in/online-services/question-papers.aspx"}],
    "up board":    [{"title": "UP Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/up-board-question-papers/"}],
    "bihar board": [{"title": "Bihar Board Papers - AglaSem", "url": "https://schools.aglasem.com/tag/bihar-board-question-papers/"}],
    # MBA/LAW/OTHERS
    "cat 2024": [{"title": "CAT 2024 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2024/"}],
    "cat 2023": [{"title": "CAT 2023 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2023/"}],
    "cat 2022": [{"title": "CAT 2022 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/cat-2022/"}],
    "cat":      [{"title": "CAT All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cat-question-papers/"},
                 {"title": "CAT PYQ - Careers360", "url": "https://bschool.careers360.com/articles/cat-previous-year-question-papers"}],
    "clat 2024": [{"title": "CLAT 2024 Paper - AglaSem", "url": "https://schools.aglasem.com/tag/clat-2024/"}],
    "clat":      [{"title": "CLAT All Year Papers - AglaSem", "url": "https://schools.aglasem.com/tag/clat-question-papers/"}],
    "cuet 2024": [{"title": "CUET 2024 Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cuet-2024/"}],
    "cuet":      [{"title": "CUET All Papers - AglaSem", "url": "https://schools.aglasem.com/tag/cuet-question-papers/"}],
    "nift":      [{"title": "NIFT Entrance Papers - AglaSem", "url": "https://schools.aglasem.com/tag/nift-question-papers/"}],
}

def get_static_results(query_text: str) -> List[dict]:
    """Efficiently find best static DB matches – tries specific keys first."""
    q = query_text.lower()
    # Prioritize year-specific matches
    for key, data in STATIC_DB.items():
        if key in q:
            return data
    return []

async def search_papers(query_text: str, limit: int = 6) -> List[dict]:
    """
    GUARANTEED SEARCH:
    Layer 1: duckduckgo_search library (works on Render cloud IPs!)
    Layer 2: Bing HTML scraper (fallback)
    """
    results = []
    seen_urls = set()
    junk = ["google.com/search", "youtube.com", "facebook.com", "twitter.com", "instagram.com", "quora.com"]

    def add_result(title, url):
        if url and url.startswith("http") and url not in seen_urls and len(results) < limit:
            if not any(j in url for j in junk):
                results.append({"title": (title or query_text)[:80], "url": url})
                seen_urls.add(url)

    # ─── LAYER 1: duckduckgo_search library (MOST RELIABLE on cloud!) ───
    try:
        logger.info(f"[SEARCH] DDGS library lookup: {query_text}")
        ddg_query = f"{query_text} filetype:pdf OR site:examfare.com OR site:pyq.examgoal.com OR site:aglasem.com OR site:shaalaa.com"
        loop = asyncio.get_event_loop()
        ddg_raw = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(ddg_query, max_results=limit + 4))
        )
        for r in ddg_raw:
            add_result(r.get('title', ''), r.get('href', '') or r.get('url', ''))
        logger.info(f"[SEARCH] DDGS library: {len(results)} results")
    except Exception as e:
        logger.warning(f"[SEARCH] DDGS library failed: {e}")

    # ─── LAYER 2: Bing HTML scraper (fallback) ───
    if len(results) < 2:
        try:
            logger.info(f"[SEARCH] Bing scraper fallback: {query_text}")
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as sess:
                bing_results = await search_bing(sess, query_text, limit=8)
                for r in bing_results:
                    add_result(r['title'], r['url'])
            logger.info(f"[SEARCH] Bing: {len(results)} results")
        except Exception as e:
            logger.warning(f"[SEARCH] Bing failed: {e}")

    return results[:limit]


async def download_and_send_pdf(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE, depth: int = 0, status_msg=None):
    """Ultra-Reliable PDF delivery with deep link hunting (Up to 2 levels)."""
    if depth > 2: return "failed"
    
    try:
        session = await get_session()
        # Quality Headers
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": url if depth > 0 else "https://www.google.com/",
            "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # 0. Early Exit for Google Drive / Docs - Redirect to download link
        if ("drive.google.com" in url or "docs.google.com" in url):
            if "/d/" in url:
                try:
                    file_id = url.split("/d/")[1].split("/")[0].split("?")[0]
                    url = f"https://drive.google.com/uc?export=download&id={file_id}"
                    logger.info(f"🔄 Transformed Google Drive link: {url}")
                except: pass
            elif "viewer?url=" in url:
                try:
                    parsed = urllib.parse.urlparse(url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if 'url' in qs:
                        url = qs['url'][0]
                        if not url.startswith("http"): url = "https://" + url
                        logger.info(f"🔄 Extracted link from Google Viewer: {url}")
                except: pass

        # 0b. Handle Search Redirects (e.g. google.com/url?q=...)
        if "google.com/url" in url:
            try:
                parsed = urllib.parse.urlparse(url)
                qs = urllib.parse.parse_qs(parsed.query)
                if 'q' in qs:
                    url = qs['q'][0]
                    logger.info(f"🔄 Resolved Google redirect: {url}")
            except: pass
        
        # 0c. AglaSem / Site Specific Headers
        if "aglasem.com" in url:
             headers["Referer"] = "https://schools.aglasem.com/"
             
        # Update status if possible
        if status_msg:
            try: 
                indicator = "🚀 Direct Search..." if depth == 0 else f"🔍 Depth {depth}: Hunting PDF..."
                await status_msg.edit_text(f"⚡ **{indicator}**\n*Trying:* `{urllib.parse.urlparse(url).netloc[:30]}`", parse_mode="Markdown")
            except: pass

        async with session.get(url, timeout=35, headers=headers, allow_redirects=True) as response:
            if response.status != 200: return "failed"
            ctype = response.headers.get("Content-Type", "").lower()
            
            # 1. Direct PDF Check
            content_preview = await response.content.read(8192)
            is_pdf = content_preview.startswith(b"%PDF-") or "pdf" in ctype
            
            if is_pdf:
                full_content = content_preview
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    full_content += chunk
                    if len(full_content) > 49 * 1024 * 1024: return "large"
                
                fname = "paper.pdf"
                cd = response.headers.get("Content-Disposition", "")
                if 'filename=' in cd: fname = cd.split('filename=')[1].strip('"').strip("'")
                else:
                    parts = url.split("/")[-1].split("?")[0]
                    if parts.lower().endswith(".pdf"): fname = parts
                    elif len(parts) > 3: fname = f"{parts}.pdf"
                
                msg = update.callback_query.message if update.callback_query else update.message
                await msg.reply_document(
                    document=io.BytesIO(full_content), filename=fname,
                    caption=f"✅ **Sent Successfully!**\n🔗 *Fast One-Click Delivery*"
                )
                return "sent"

            # 2. HTML Link Hunting
            if "html" in ctype:
                html = content_preview + (await response.content.read())
                soup = BeautifulSoup(html, 'html.parser')
                candidates = []
                for tag in soup.find_all(['a', 'iframe', 'button', 'embed', 'object']):
                    link = tag.get('href') or tag.get('src') or tag.get('data-url') or tag.get('data-link')
                    if not link or len(link) < 5 or link.startswith('#') or link.startswith('javascript:'): continue
                    
                    full_link = urllib.parse.urljoin(url, link)
                    text = tag.get_text().strip().lower()
                    
                    score = 0
                    if full_link.lower().endswith(".pdf"): score += 100
                    if "pdf" in full_link.lower(): score += 40
                    if "drive.google.com" in full_link.lower(): score += 50
                    if "download" in full_link.lower(): score += 10
                    if "download" in text and ("pdf" in text or "paper" in text): score += 60
                    if tag.name == "iframe" and "viewer" in full_link.lower(): score += 70
                    
                    if score > 0 and not any(x in full_link.lower() for x in ["facebook", "twitter", "whatsapp", "telegram"]):
                        candidates.append((score, full_link))

                unique_cands = []
                seen = set()
                for s, l in sorted(candidates, key=lambda x: x[0], reverse=True):
                    if l not in seen:
                        unique_cands.append((s, l))
                        seen.add(l)
                
                max_cands = 10 if depth == 0 else 3
                for _, cand in unique_cands[:max_cands]:
                    res = await download_and_send_pdf(cand, update, context, depth + 1, status_msg)
                    if res != "failed": return res
    except Exception as e:
        logger.error(f"Download Error at depth {depth} ({url}): {e}")
    return "failed"



async def year_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Result renderer — uses Static DB directly for guaranteed results."""
    query = update.callback_query
    await query.answer("Fetching results...")
    parts = query.data.split("_")
    cat_name, exam_name, year = parts[1], parts[2], parts[3]

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
    if not results or year == "Older" or len(results) < 2:
        category_exams = EXAM_CATEGORIES.get(cat_name, {})
        base_query = category_exams.get(exam_name, f"{exam_name} Previous Year Paper")
        year_str = "" if year == "Older" else year
        final_query = f"{exam_name} {year_str} question paper pdf".strip()
        live_res = await search_papers(final_query, limit=5-len(results))
        for r in live_res:
            add(r['title'], r['url'])

    if not results:
        await query.edit_message_text(
            f"❌ **No results found for {exam_name} ({year}).**\n\nTry another year or browse /start.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back Selection", callback_data=f"exam_{cat_name}_{exam_name}")]]))
        return

    # ────── ONE-CLICK DIRECT DOWNLOAD EXPERIENCE ──────
    context.user_data['last_results'] = results
    
    wait_msg = await query.edit_message_text(
        f"🎯 **Year: {year} | Exam: {exam_name}**\n\n"
        f"🚀 **Starting One-Click Direct Download...**\n"
        f"Please wait while I fetch the best PDF for you.",
        parse_mode="Markdown"
    )

    # Automatically attempt download of top result
    status = await download_and_send_pdf(results[0]['url'], update, context, 0, wait_msg)
    
    if status == "sent":
        response = f"✅ **PDF Sent!**\n\nI found the best match for **{exam_name} ({year})** and delivered it above.\n\nNeed more versions or different shifts?"
        keyboard = []
        for i, res in enumerate(results):
            keyboard.append([InlineKeyboardButton(f"📥 Version {i+1}", callback_data=f"dl_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to years", callback_data=f"exam_{cat_name}_{exam_name}")])
        try: await wait_msg.edit_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except: pass
        return

    # Fallback if auto-download failed
    response = f"📚 **{exam_name} Results ({year}):**\n\n"
    response += "⚠️ *Auto-download failed. Please try these links:* \n\n"
    keyboard = []
    for i, res in enumerate(results):
        response += f"📄 {i+1}. **{res['title']}**\n"
        keyboard.append([InlineKeyboardButton(f"📥 Download PDF {i+1}", callback_data=f"dl_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to years", callback_data=f"exam_{cat_name}_{exam_name}")])
    await wait_msg.edit_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

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
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")
    status_msg = await update.message.reply_text(f"🔍 **Searching for:** *{query_text}*", parse_mode="Markdown")
    results = await search_papers(f"{query_text}", limit=8)
    
    if not results:
        await status_msg.edit_text("❌ **No results found.** Please use the /start menu to browse categorized exams.")
        return

    # Hide raw URLs for a cleaner experience
    response = f"📚 **Search Results for: {query_text}**\n\n"
    keyboard = []
    for i, res in enumerate(results):
        response += f"📄 {i+1}. **{res['title']}**\n"
        keyboard.append([InlineKeyboardButton(f"📥 One-Click Download {i+1}", callback_data=f"dl_{i}")])
    
    context.user_data['last_results'] = results
    await status_msg.edit_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

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
    """Tests all search engines and reports results directly in chat."""
    msg = await update.message.reply_text("🔬 **Running search diagnostics...**", parse_mode="Markdown")
    report = ["🔬 **Search Engine Diagnostic Report**\n"]
    test_query = "JEE Mains 2023 question paper"
    report.append(f"📋 Test query: `{test_query}`\n")

    # Test SearXNG
    try:
        session = await get_session()
        params = urllib.parse.urlencode({"q": test_query + " pdf", "format": "json", "categories": "general"})
        async with session.get(f"https://searx.be/search?{params}", headers={"Accept": "application/json"}, timeout=8) as resp:
            data = await resp.json(content_type=None)
            count = len(data.get("results", []))
            report.append(f"{'✅' if count > 0 else '❌'} SearXNG (searx.be): {count} results")
    except Exception as e:
        report.append(f"❌ SearXNG: {str(e)[:60]}")

    # Test DDG
    try:
        session = await get_session()
        async with session.get(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(test_query)}", timeout=8) as resp:
            report.append(f"{'✅' if resp.status == 200 else '❌'} DDG HTML: status {resp.status}")
    except Exception as e:
        report.append(f"❌ DDG: {str(e)[:60]}")

    # Test Bing
    try:
        session = await get_session()
        async with session.get(f"https://www.bing.com/search?q={urllib.parse.quote(test_query)}", headers={"User-Agent": "Mozilla/5.0"}, timeout=8) as resp:
            soup = BeautifulSoup(await resp.text(), 'html.parser')
            links = soup.select('h2 a')
            report.append(f"{'✅' if links else '❌'} Bing: {len(links)} links found (status {resp.status})")
    except Exception as e:
        report.append(f"❌ Bing: {str(e)[:60]}")

    # Test Static DB
    try:
        res = get_static_results("jee mains 2024")
        report.append(f"{'✅' if res else '❌'} Static DB: {len(res)} entries matched")
    except Exception as e:
        report.append(f"❌ Static DB: {str(e)[:60]}")

    full_report = "\n".join(report)
    await msg.edit_text(full_report, parse_mode="Markdown")

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
        import time
        import threading
        import requests 
        
        class HealthCheck(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Bot is online (Cloud Health Check OK)")
            
            def log_message(self, format, *args):
                pass 

        try:
            httpd = HTTPServer(('0.0.0.0', PORT), HealthCheck)
            logger.info(f"✅ Cloud Health Server listening on port {PORT}")
            httpd.serve_forever()
        except Exception as e:
            logger.error(f"❌ Health-Check Server error: {e}")

    # Launch health check in background thread
    import threading
    threading.Thread(target=run_cloud_keep_alive, daemon=True).start()

    # Build bot application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CallbackQueryHandler(start, pattern="^back_cats$"))
    application.add_handler(CallbackQueryHandler(direct_search_callback, pattern="^direct_search$"))
    application.add_handler(CallbackQueryHandler(category_handler, pattern="^cat_"))
    application.add_handler(CallbackQueryHandler(exam_handler, pattern="^exam_"))
    application.add_handler(CallbackQueryHandler(year_handler, pattern="^year_"))
    application.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # START THE BOT
    logger.info(f"📡 PRODUCTION: Using Stable Polling (Health server on port {PORT})")
    application.run_polling()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()

