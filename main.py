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
    }
}

YEARS = ["2024", "2023", "2022", "2021", "2020", "2019", "2018", "Older"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows main categories."""
    # VERSION IDENTIFICATION
    version = "v6.3 Render Ultra"
    text = (
        f"👋 **Welcome to the Professional Exam Assistant Bot {version}**\n\n"
        "I can help you find and download Previous Year Question Papers (PYQs) for almost all major Indian exams.\n\n"
        "Please select an **Exam Category** below to get started:"
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
        session_instance = aiohttp.ClientSession()
    return session_instance

async def get_direct_pdf_link(session, title: str, url: str) -> dict:
    """Try to find a direct PDF link with a 12s timeout."""
    if url.lower().endswith(".pdf"): return {"title": title, "url": url}
    try:
        # Improved headers for better detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with session.get(url, timeout=12.0, headers=headers) as response:
            if response.status == 200:
                ctype = response.headers.get("Content-Type", "").lower()
                if "pdf" in ctype: return {"title": title, "url": url}

                # 2. Handle common PDF viewer redirects
                if "google.com/viewer" in url or "docs.google.com/viewer" in url:
                    parsed = urllib.parse.urlparse(url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if 'url' in qs:
                        pdf_url = qs['url'][0]
                        if not pdf_url.startswith("http"): pdf_url = "https://" + pdf_url
                        return {"title": title, "url": pdf_url}

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Broaden the search for PDF candidates
                candidates = []
                for a in soup.find_all(['a', 'iframe'], href=True, src=True, limit=120):
                    link = a.get('href') or a.get('src')
                    if not link: continue
                    full_url = urllib.parse.urljoin(url, link)
                    
                    # Score the link
                    score = 0
                    if full_url.lower().endswith(".pdf"): score += 10
                    if "pdf" in full_url.lower(): score += 5
                    if "download" in full_url.lower(): score += 3
                    if "paper" in full_url.lower(): score += 2
                    
                    if score > 0:
                        candidates.append((score, full_url))
                
                if candidates:
                    # Sort by score descending
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    return {"title": title, "url": candidates[0][1]}
    except: pass
    return None

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
    """Find best static DB matches — tries longest keys first for specificity."""
    q = query_text.lower().strip()
    matched = []
    seen = set()
    # Try longest keys first so "jee mains 2024" matches before "jee mains"
    for key in sorted(STATIC_DB.keys(), key=len, reverse=True):
        if key in q:
            for item in STATIC_DB[key]:
                if item['url'] not in seen:
                    matched.append(item)
                    seen.add(item['url'])
            if len(matched) >= 4:
                break
    return matched[:6]

async def search_papers(query_text: str, limit: int = 6) -> List[dict]:
    """
    GUARANTEED SEARCH: Static DB (PRIMARY) -> DDGS Library -> Bing Scraper.
    Static DB covers ALL exam categories — works 100% on Render cloud IPs.
    """
    results = []
    seen_urls = set()

    def add_result(title, url):
        junk = ["google.com/search", "youtube.com", "facebook.com", "twitter.com", "instagram.com"]
        if url and url.startswith("http") and url not in seen_urls and len(results) < limit:
            if not any(j in url for j in junk):
                results.append({"title": (title or query_text)[:80], "url": url})
                seen_urls.add(url)

    # ─── LAYER 1: Static DB (ALWAYS first — no network needed) ───
    logger.info(f"[SEARCH] Static DB lookup: {query_text}")
    for item in get_static_results(query_text):
        add_result(item['title'], item['url'])
    logger.info(f"[SEARCH] Static DB: {len(results)} results")

    # ─── LAYER 2: DDGS library (handles cloud IPs better than scraping) ───
    if len(results) < 2:
        try:
            from duckduckgo_search import DDGS
            logger.info(f"[SEARCH] DDGS lookup: {query_text}")
            ddgs_results = await asyncio.to_thread(
                lambda: list(DDGS().text(f"{query_text} question paper pdf site:aglasem.com OR site:careers360.com", max_results=8))
            )
            for r in ddgs_results:
                add_result(r.get('title', ''), r.get('href', ''))
            logger.info(f"[SEARCH] DDGS: {len(ddgs_results)} results")
        except Exception as e:
            logger.warning(f"[SEARCH] DDGS failed: {e}")

    # ─── LAYER 3: Bing HTML scraper (last resort) ───
    if len(results) < 2:
        try:
            logger.info(f"[SEARCH] Bing scraper: {query_text}")
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as sess:
                bing_results = await search_bing(sess, query_text, limit=8)
                for r in bing_results:
                    add_result(r['title'], r['url'])
            logger.info(f"[SEARCH] Bing: {len(bing_results)} results")
        except Exception as e:
            logger.warning(f"[SEARCH] Bing failed: {e}")

    if results:
        results = results[:limit]
        async with aiohttp.ClientSession() as res_sess:
            tasks = [get_direct_pdf_link(res_sess, r['title'], r['url']) for r in results]
            final_res = await asyncio.gather(*tasks, return_exceptions=True)
            return [r if (isinstance(r, dict) and r.get('url')) else orig for r, orig in zip(final_res, results)]

    return []


async def download_and_send_pdf(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE, depth: int = 0):
    """Ultra-Reliable PDF delivery with deep link hunting (Up to 2 levels)."""
    if depth > 2: return False # Deep enough to handle most "Click -> Button -> PDF" sites
    
    try:
        session = await get_session()
        # High-Quality Headers (mimics a real Chrome browser on Windows)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": url if depth > 0 else "https://www.google.com/",
            "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # Extended timeout (45s) for slow educational portals
        async with session.get(url, timeout=45, headers=headers, allow_redirects=True) as response:
            if response.status == 200:
                ctype = response.headers.get("Content-Type", "").lower()
                
                # Check for PDF magic bytes (streaming read)
                content_preview = await response.content.read(2048)
                is_pdf = content_preview.startswith(b"%PDF-") or "pdf" in ctype
                
                if is_pdf:
                    # Read the rest of the content
                    full_content = content_preview + (await response.content.read())
                    if len(full_content) < 48 * 1024 * 1024:
                        cd = response.headers.get("Content-Disposition", "")
                        fname = "exam_paper.pdf"
                        if 'filename=' in cd:
                            fname = cd.split('filename=')[1].strip('"').strip("'")
                        else:
                            # Heuristic: extract from URL
                            parts = url.split("/")[-1].split("?")[0]
                            if parts.lower().endswith(".pdf"): fname = parts
                            else: fname = f"{parts}.pdf" if parts else "paper.pdf"
                        
                        msg = update.callback_query.message if update.callback_query else update.message
                        await msg.reply_document(
                            document=io.BytesIO(full_content),
                            filename=fname,
                            caption=f"✅ **Sent Successfully!**\n🔗 *Fast Direct Download*"
                        )
                        return True
                    else: return "large"

                # 2. Page Parsing & Landing Page Handling
                if "html" in ctype:
                    # Read HTML (don't miss anything)
                    html = content_preview + (await response.content.read())
                    soup = BeautifulSoup(html, 'html.parser')
                    candidates = []
                    
                    # Look for hidden links and "Download" buttons
                    for tag in soup.find_all(['a', 'iframe', 'button', 'embed', 'object']):
                        link = tag.get('href') or tag.get('src') or tag.get('data-url') or tag.get('data-link')
                        if not link or link.startswith('#') or link.startswith('javascript:'): continue
                        
                        full_link = urllib.parse.urljoin(url, link)
                        text = tag.get_text().strip().lower()
                        
                        score = 0
                        # Boost score based on URL and text indicators
                        if full_link.lower().endswith(".pdf"): score += 20
                        if "pdf" in full_link.lower(): score += 10
                        if "download" in full_link.lower(): score += 5
                        if "paper" in full_link.lower(): score += 3
                        
                        # Platform boosts (Trusted PYQ sources)
                        trusted_sites = ["aglasem", "byjus", "careers360", "collegedunia", "shiksha", "vedantu", "sarkariexam", "sarkariresult"]
                        if any(site in full_link.lower() for site in trusted_sites):
                            score += 15
                        
                        # Text triggers
                        if "download" in text and ("pdf" in text or "paper" in text): score += 12
                        if "click" in text and "here" in text: score += 5
                        if "direct" in text: score += 5
                        if "official" in text: score += 3
                        if "solution" in text: score += 4

                        # Filter out common garbage
                        if score > 0 and not any(x in full_link.lower() for x in ["social", "login", "signup", "contact", "about", "register", "policy"]):
                            candidates.append((score, full_link))

                    # Deduplicate and sort
                    seen = set()
                    unique_candidates = []
                    for s, l in candidates:
                        if l not in seen:
                            unique_candidates.append((s, l))
                            seen.add(l)
                    
                    unique_candidates.sort(key=lambda x: x[0], reverse=True)
                    
                    # Try top 6 candidates (higher depth allows more exploration)
                    for _, cand in unique_candidates[:7]:
                        logger.info(f"Depth {depth} -> Hunting PDF at: {cand}")
                        if await download_and_send_pdf(cand, update, context, depth + 1):
                            return True
    except Exception as e:
        logger.error(f"Reliability Error at {url}: {e}")
    return False

async def year_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Speed-optimized result rendering."""
    query = update.callback_query
    await query.answer("Fetching results...") # Instant feedback
    parts = query.data.split("_")
    cat_name, exam_name, year = parts[1], parts[2], parts[3]
    
    # Use the full descriptive query from EXAM_CATEGORIES for better search results
    category_exams = EXAM_CATEGORIES.get(cat_name, {})
    base_query = category_exams.get(exam_name, f"{exam_name} Previous Year Question Paper")
    year_str = "" if year == "Older" else year
    final_query = f"{base_query} {year_str}".strip()

    await query.edit_message_text(f"⚡ **Searching {exam_name} ({year})...**", parse_mode="Markdown")
    
    # Show typing indicator for better UX
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
    
    results = await search_papers(final_query)
    if not results:
        await query.edit_message_text(f"❌ **No results.** Please try another year.", 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"exam_{cat_name}_{exam_name}")]]))
        return

    response = f"📚 **Top Results ({year}):**\n\n"
    keyboard = []
    for i, res in enumerate(results):
        response += f"📄 {i+1}. [{res['title']}]({res['url']})\n\n"
        keyboard.append([InlineKeyboardButton(f"🚀 Download {i+1}", callback_data=f"dl_{i}")])
    
    context.user_data['last_results'] = results
    keyboard.append([InlineKeyboardButton("🔙 Back to Year Selection", callback_data=f"exam_{cat_name}_{exam_name}")])
    await query.edit_message_text(response, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

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

    response = f"📚 **Search Results for: {query_text}**\n\n"
    keyboard = []
    for i, res in enumerate(results):
        response += f"📄 {i+1}. [{res['title']}]({res['url']})\n\n"
        keyboard.append([InlineKeyboardButton(f"🚀 Download PDF {i+1}", callback_data=f"dl_{i}")])
    
    context.user_data['last_results'] = results
    await status_msg.edit_text(response, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refined download handler with informative errors."""
    query = update.callback_query
    await query.answer("Preparing download...")
    idx = int(query.data.split("_")[1])
    
    # Send 'upload_document' action to show progress
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="upload_document")
    
    results = context.user_data.get('last_results', [])
    
    if idx < len(results):
        url = results[idx]['url']
        wait_msg = await query.message.reply_text(f"⚡ **Checking link...**")
        success = await download_and_send_pdf(url, update, context)
        await wait_msg.delete()
        
        if success == "large":
            await query.message.reply_text(
                f"📂 **File is too large!**\n\n"
                f"The PDF is larger than 50MB, which is the limit for Telegram bots. "
                f"Please download it manually using the link below:\n\n"
                f"🔗 **[Download Large Paper]({url})**",
                parse_mode="Markdown"
            )
        elif not success:
            await query.message.reply_text(
                f"⚠️ **Note:** Direct PDF delivery failed for this link.\n\n"
                f"This usually happens when the website has strict bot protection or requires manual verification.\n\n"
                f"🔗 **[Click here to open the paper in browser]({url})**",
                parse_mode="Markdown",
                disable_web_page_preview=False
            )

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

    # Test DDGS library
    try:
        from duckduckgo_search import DDGS
        res = await asyncio.to_thread(lambda: list(DDGS().text(test_query, max_results=5)))
        report.append(f"{'✅' if res else '❌'} DDGS library: {len(res)} results")
    except Exception as e:
        report.append(f"❌ DDGS: {str(e)[:60]}")

    # Test Bing
    try:
        session = await get_session()
        async with session.get(f"https://www.bing.com/search?q={urllib.parse.quote(test_query)}", headers={"User-Agent": "Mozilla/5.0"}, timeout=8) as resp:
            soup = BeautifulSoup(await resp.text(), 'html.parser')
            links = soup.select('h2 a')
            report.append(f"{'✅' if links else '❌'} Bing: {len(links)} links found (status {resp.status})")
    except Exception as e:
        report.append(f"❌ Bing: {str(e)[:60]}")

    # Test Google lib
    try:
        from googlesearch import search as gsearch
        res = await asyncio.to_thread(lambda: list(gsearch(test_query, num_results=3, sleep_interval=0)))
        report.append(f"{'✅' if res else '❌'} Google lib: {len(res)} results")
    except Exception as e:
        report.append(f"❌ Google lib: {str(e)[:60]}")

    full_report = "\n".join(report)
    await msg.edit_text(full_report, parse_mode="Markdown")

def main():
    if not BOT_TOKEN:
        logger.error("❌ ERROR: TELEGRAM_BOT_TOKEN is missing!")
        print("❌ ERROR: TELEGRAM_BOT_TOKEN is missing!")
        # If no token, raise an error so Render logs capture it properly
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables.")
        
    logger.info("🚀 Starting Bot Application...")
    
    # 🌟 RENDER DEPLOYMENT HACK: Ensures the bot always listens to a Port
    PORT = int(os.environ.get("PORT", "10000"))
    
    async def post_init(application):
        """Tries to stay awake and ensures port binding based on mode."""
        external_url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL")
        
        # 1. Start Health-Check Server ONLY if in Polling Mode (Avoids port conflict)
        if not external_url:
            try:
                app = web.Application()
                app.router.add_get('/', lambda r: web.Response(text="Bot is online!"))
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, '0.0.0.0', PORT)
                await site.start()
                logger.info(f"✅ Polling mode: Keep-alive server started on port {PORT}")
            except Exception as se:
                logger.error(f"❌ Failed to start health server: {se}")

        # 2. Start Self-Pinger (Works in both modes to reduce Cold Starts)
        if external_url:
            async def self_pinger():
                await asyncio.sleep(30) # Wait for startup to complete
                while True:
                    try:
                        async with aiohttp.ClientSession() as sess:
                            async with sess.get(external_url, timeout=15) as resp:
                                logger.info(f"📡 Heartbeat (Self-ping): {resp.status}")
                    except Exception as pe:
                        logger.warning(f"⚠️ Heartbeat failed: {pe}")
                    await asyncio.sleep(600) # Every 10 minutes
            
            asyncio.create_task(self_pinger())
            logger.info(f"⚡ Self-pinger active for: {external_url}")

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Base commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(start, pattern="^back_cats$"))
    application.add_handler(CallbackQueryHandler(direct_search_callback, pattern="^direct_search$"))
    application.add_handler(CallbackQueryHandler(category_handler, pattern="^cat_"))
    application.add_handler(CallbackQueryHandler(exam_handler, pattern="^exam_"))
    application.add_handler(CallbackQueryHandler(year_handler, pattern="^year_"))
    application.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    
    # Message Handler for Direct Search (Free Text)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # PORT Binding is CRITICAL for Render
    PORT = int(os.environ.get("PORT", "10000"))
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL") 

    if WEBHOOK_URL or "RENDER" in os.environ or "PORT" in os.environ:
        # Use Webhooks if on Render/Cloud (Required to keep Render service 'Live')
        logger.info(f"✅ Starting in PRODUCTION mode (Webhook) on port {PORT}")
        w_url = WEBHOOK_URL or "https://pyq-telegram-bot.onrender.com" # Fallback guess if not set
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{w_url}/{BOT_TOKEN}"
        )
    else:
        # Standard Polling for local development (Laptop)
        logger.info("📡 Starting in LOCAL mode (Polling)")
        application.run_polling()

if __name__ == "__main__":
    main()
