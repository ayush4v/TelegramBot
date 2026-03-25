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
        "👋 **Welcome to the Professional Exam Assistant Bot v5.0 Ultra**\n\n"
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
    """Try to find a direct PDF link with a 5s timeout."""
    if url.lower().endswith(".pdf"): return {"title": title, "url": url}
    try:
        # Increased timeout to 5 seconds for better reliability on Indian sites
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36"}
        async with session.get(url, timeout=5.0, headers=headers) as response:
            if response.status == 200:
                # 1. If the URL itself serves a PDF (checked by content-type)
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

async def search_papers(query: str, limit: int = 6) -> List[dict]:
    """
    Robust multi-engine search. Uses duckduckgo-search library as primary
    (uses DDG's internal API, NOT scraping — works on all cloud IPs).
    Multiple fallbacks ensure results are always found.
    """
    results = []
    seen_urls = set()

    def add_result(title, url):
        if url and url.startswith("http") and url not in seen_urls and len(results) < limit:
            results.append({"title": (title or query)[:80], "url": url})
            seen_urls.add(url)

    # ─── ENGINE 1: duckduckgo-search library (PRIMARY - cloud-safe) ───
    logger.info(f"🔎 [Engine 1] DDGS library: {query}")
    try:
        from duckduckgo_search import DDGS
        search_q = f"{query} filetype:pdf"
        ddgs_results = await asyncio.to_thread(
            lambda: list(DDGS().text(search_q, max_results=12, timelimit=None))
        )
        for r in ddgs_results:
            add_result(r.get("title", query), r.get("href", ""))
        logger.info(f"[Engine 1] DDGS found {len(results)} results")
    except Exception as e:
        logger.error(f"[Engine 1] DDGS failed: {e}")

    # ─── ENGINE 2: DDGS without filetype filter (if filetype:pdf gave 0) ───
    if not results:
        logger.info(f"🔎 [Engine 2] DDGS (no filetype): {query}")
        try:
            from duckduckgo_search import DDGS
            ddgs_results2 = await asyncio.to_thread(
                lambda: list(DDGS().text(f"{query} question paper pdf download", max_results=12))
            )
            for r in ddgs_results2:
                add_result(r.get("title", query), r.get("href", ""))
            logger.info(f"[Engine 2] DDGS (no filetype) found {len(results)} results")
        except Exception as e:
            logger.error(f"[Engine 2] DDGS no-filter failed: {e}")

    # ─── ENGINE 3: Bing scraping ───
    if not results:
        logger.info(f"🔎 [Engine 3] Bing: {query}")
        try:
            session = await get_session()
            bing_url = f"https://www.bing.com/search?q={urllib.parse.quote(query + ' pdf previous year paper')}&count=15"
            h3 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "en-IN,en;q=0.9",
            }
            async with session.get(bing_url, headers=h3, timeout=10) as resp:
                if resp.status == 200:
                    b_soup = BeautifulSoup(await resp.text(), 'html.parser')
                    for a in b_soup.select('h2 a, .b_algo h2 a')[:10]:
                        add_result(a.get_text(strip=True), a.get('href', ''))
            logger.info(f"[Engine 3] Bing found {len(results)} results")
        except Exception as e:
            logger.error(f"[Engine 3] Bing failed: {e}")

    # ─── ENGINE 4: Google (googlesearch-python) ───
    if not results:
        logger.info(f"🔎 [Engine 4] Google lib: {query}")
        try:
            from googlesearch import search as gsearch
            gs_results = await asyncio.to_thread(
                lambda: list(gsearch(f"{query} filetype:pdf", num_results=10, sleep_interval=1))
            )
            for link in gs_results:
                if isinstance(link, str):
                    title = link.split('/')[-1].split('.pdf')[0].replace('-', ' ').replace('_', ' ')[:60] or query[:50]
                    add_result(title, link)
                elif hasattr(link, 'url'):
                    add_result(getattr(link, 'title', query[:50]), link.url)
            logger.info(f"[Engine 4] Google found {len(results)} results")
        except Exception as e:
            logger.error(f"[Engine 4] Google failed: {e}")

    # ─── ENGINE 5: Trusted Indian Exam Sites (guaranteed last resort) ───
    if not results:
        logger.info(f"🔎 [Engine 5] Trusted Indian sites: {query}")
        q_enc = urllib.parse.quote(query)
        trusted_sites = [
            ("AglaSem", f"https://aglasem.com/?s={q_enc}"),
            ("Examfare", f"https://www.examfare.com/?s={q_enc}"),
            ("SarkariExam", f"https://sarkariexam.com/?s={q_enc}"),
            ("myCBSEguide", f"https://mycbseguide.com/search/?q={q_enc}"),
            ("StudiesToday", f"https://www.studiestoday.com/search/node/{q_enc}"),
        ]
        try:
            session = await get_session()
            for site_name, site_url in trusted_sites:
                if len(results) >= limit: break
                try:
                    async with session.get(site_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8) as resp:
                        if resp.status == 200:
                            s_soup = BeautifulSoup(await resp.text(), 'html.parser')
                            for a in s_soup.find_all('a', href=True)[:50]:
                                href = urllib.parse.urljoin(site_url, a['href'])
                                txt = a.get_text(strip=True)
                                score = 0
                                if href.lower().endswith('.pdf'): score += 10
                                if 'pdf' in href.lower(): score += 5
                                if any(w in txt.lower() for w in ['paper', 'question', 'exam', 'pdf', 'pyq']): score += 3
                                if score >= 3:
                                    add_result(f"{site_name}: {txt}", href)
                except Exception as se:
                    logger.warning(f"[Engine 5] {site_name} failed: {se}")
        except Exception as e:
            logger.error(f"[Engine 5] overall failed: {e}")
        logger.info(f"[Engine 5] Trusted sites found {len(results)} results")

    # ─── PDF Resolution: upgrade landing pages → direct PDFs ───
    if results:
        logger.info(f"🔗 Resolving {len(results)} URLs to direct PDFs...")
        try:
            session = await get_session()
            tasks = [get_direct_pdf_link(session, r['title'], r['url']) for r in results]
            resolved = await asyncio.gather(*tasks, return_exceptions=True)
            final, final_seen = [], set()
            for orig, res in zip(results, resolved):
                if isinstance(res, dict) and res.get('url') and res['url'] not in final_seen:
                    final.append(res); final_seen.add(res['url'])
                elif orig['url'] not in final_seen:
                    final.append(orig); final_seen.add(orig['url'])
            results = final[:limit]
        except Exception as e:
            logger.error(f"PDF resolution failed: {e}")

    logger.info(f"✅ Search complete — {len(results)} results for: {query}")
    return results

async def download_and_send_pdf(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE, depth: int = 0):
    """Ultra-Reliable PDF delivery with deep link hunting (Up to 2 levels)."""
    if depth > 2: return False # Deep enough to handle most "Click -> Button -> PDF" sites
    
    try:
        session = await get_session()
        # Full browser-like headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Referer": url if depth > 0 else "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8"
        }
        
        async with session.get(url, timeout=40, headers=headers, allow_redirects=True) as response:
            if response.status == 200:
                ctype = response.headers.get("Content-Type", "").lower()
                
                # Check for PDF magic bytes in the first few bytes (streaming read)
                content_preview = await response.content.read(1024)
                is_pdf = content_preview.startswith(b"%PDF-") or "pdf" in ctype
                
                # 1. Handling Direct PDF
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
    PORT = int(os.environ.get("PORT", "10000"))
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL") 

    if WEBHOOK_URL:
        # Use Webhooks if on Render/Cloud Run (High Performance)
        logger.info(f"✅ Starting in WEBHOOK mode on port {PORT}")
        logger.info(f"🔗 External URL: {WEBHOOK_URL}")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # Standard Polling for local development (Laptop)
        logger.info("📡 Starting in POLLING mode (Local Desktop)")
        application.run_polling()

if __name__ == "__main__":
    main()
