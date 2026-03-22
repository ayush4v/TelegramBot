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
    text = (
        "👋 **Welcome to the Professional Exam Assistant Bot**\n\n"
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
    """Follow a landing page and try to find a direct PDF link (Async Parallel)."""
    if url.lower().endswith(".pdf"): return {"title": title, "url": url}
    try:
        async with session.get(url, timeout=7) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if href.lower().endswith(".pdf"):
                        return {"title": title, "url": urllib.parse.urljoin(url, href)}
    except: pass
    return None

async def search_papers(query: str, limit: int = 8) -> List[dict]:
    """Blazing fast parallel search with deep-link resolution."""
    results = []
    search_query = f"{query} question paper pdf direct download"
    search_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(search_query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        session = await get_session()
        async with session.get(search_url, headers=headers, timeout=8) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                
                tasks = []
                for a in soup.find_all('a', class_='result__a')[:15]: # Take top 15 candidates
                    href = a.get('href', '')
                    if "uddg=" in href:
                        href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get('uddg', [href])[0]
                    if href.startswith("//"): href = "https:" + href
                    title = a.get_text().strip().replace("PDF", "").strip()[:50]
                    
                    # Create parallel task for resolution
                    tasks.append(get_direct_pdf_link(session, title, href))
                
                # Execute all tasks in parallel! (The magic of speed)
                resolved_results = await asyncio.gather(*tasks)
                
                # Filter out None and deduplicate
                seen_urls = set()
                for res in resolved_results:
                    if res and res['url'] not in seen_urls:
                        results.append(res)
                        seen_urls.add(res['url'])
                    if len(results) >= limit: break
    except Exception as e: logger.error(f"Parallel Search Error: {e}")
    return results

async def download_and_send_pdf(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Secure and verified PDF delivery with signature checking."""
    try:
        session = await get_session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
        async with session.get(url, timeout=20, headers=headers) as response:
            if response.status == 200:
                # 1. Verify it's actually a PDF by checking headers
                ctype = response.headers.get("Content-Type", "").lower()
                content = await response.read()
                
                # 2. Check for PDF Magic Bytes (%PDF-)
                is_pdf = content.startswith(b"%PDF-")
                
                if is_pdf:
                    if len(content) < 48 * 1024 * 1024: # Under 48MB
                        file_name = url.split("/")[-1].split("?")[0] or "exam_paper.pdf"
                        if not file_name.lower().endswith(".pdf"): file_name += ".pdf"
                        
                        msg = update.callback_query.message if update.callback_query else update.message
                        await msg.reply_document(
                            document=io.BytesIO(content), 
                            filename=file_name, 
                            caption=f"✅ **Verified PDF Document**\n🔗 *Source: {url}*"
                        )
                        return True
                    else:
                        logger.warning(f"File too large: {len(content)}")
                else:
                    logger.warning(f"Not a valid PDF at {url}. Headers: {ctype}")
    except Exception as e:
        logger.error(f"Downloader Error: {e}")
    return False

async def year_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Speed-optimized result rendering."""
    query = update.callback_query
    await query.answer("Fetching results...") # Instant feedback
    parts = query.data.split("_")
    cat_name, exam_name, year = parts[1], parts[2], parts[3]
    
    final_query = f"{exam_name} {year} question paper"
    await query.edit_message_text(f"⚡ **Fetching {exam_name} ({year})...**", parse_mode="Markdown")
    
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
    await query.answer("Fetching file...")
    idx = int(query.data.split("_")[1])
    results = context.user_data.get('last_results', [])
    
    if idx < len(results):
        url = results[idx]['url']
        wait_msg = await query.message.reply_text(f"⚡ **Checking link...**")
        success = await download_and_send_pdf(url, update, context)
        await wait_msg.delete()
        if not success:
            await query.message.reply_text(
                f"⚠️ **Note:** Direct PDF delivery is not possible for this link (it might be a website or require manual download).\n\n"
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

def main():
    if not BOT_TOKEN:
        logger.error("❌ CRITICAL: TELEGRAM_BOT_TOKEN not found in environment variables!")
        print("❌ CRITICAL: TELEGRAM_BOT_TOKEN not found in environment variables!")
        # Don't exit, stay alive for 60s so logs can be read in Render
        import time
        time.sleep(60) 
        return
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Base commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(start, pattern="^back_cats$"))
    application.add_handler(CallbackQueryHandler(direct_search_callback, pattern="^direct_search$"))
    application.add_handler(CallbackQueryHandler(category_handler, pattern="^cat_"))
    application.add_handler(CallbackQueryHandler(exam_handler, pattern="^exam_"))
    application.add_handler(CallbackQueryHandler(year_handler, pattern="^year_"))
    application.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))
    
    # Message Handler for Direct Search (Free Text)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Cloud Run Webhook Support
    PORT = int(os.environ.get("PORT", "8080"))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 

    if WEBHOOK_URL:
        # Use Webhooks if WEBHOOK_URL is provided (Cloud Run environment / Render)
        logger.info(f"Bot is starting with Webhooks on port {PORT}...")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # --- Start Render/Cloud Run Health Check Server using aiohttp ---
        async def health_check_app():
            app = web.Application()
            app.router.add_get('/', lambda r: web.Response(text="Bot is alive!"))
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', PORT)
            await site.start()
            logger.info(f"✅ Health check server started on port {PORT}")
            
        # Add the health check to the bot's loop
        loop = asyncio.get_event_loop()
        loop.create_task(health_check_app())
        
        # Standard Polling for local development
        logger.info(f"Bot is starting with Polling on port {PORT}...")
        application.run_polling()

if __name__ == "__main__":
    main()
