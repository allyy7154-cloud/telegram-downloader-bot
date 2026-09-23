import os
import re
import yt_dlp
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, MessageHandler,
    filters, CommandHandler, CallbackQueryHandler
)
from telegram.constants import ChatMemberStatus

# ============================================================
#  الإعدادات
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ضع_التوكن_الجديد_هنا")

CHANNEL_USERNAME = "@botahmedna"
CHANNEL_LINK     = "https://t.me/botahmedna"

DOWNLOAD_PATH = "/tmp/downloads"
# ============================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

os.makedirs(DOWNLOAD_PATH, exist_ok=True)


# ---------------- أدوات ----------------
def extract_url(text: str):
    if not text:
        return None
    m = re.search(r'https?://[^\s]+', text)
    return m.group(0) if m else None


async def is_subscribed(context, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception as e:
        logger.error(f"فشل فحص الاشتراك: {e}")
        return False


def subscribe_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 اشترك بالقناة", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data="check_sub")],
    ])


async def download_media(url: str) -> str:
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_PATH}/%(id)s.%(ext)s',
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'playlist_items': '1',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not os.path.exists(filename):
            files = [os.path.join(DOWNLOAD_PATH, f)
                     for f in os.listdir(DOWNLOAD_PATH)]
            if files:
                filename = max(files, key=os.path.getctime)
        return filename


# ---------------- الهاندلرز ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(context, user_id):
        await update.message.reply_text(
            "🔒 لتستخدم البوت، لازم تكون مشترك بقناتنا أولاً:",
            reply_markup=subscribe_keyboard(),
        )
        return
    await update.message.reply_text(
        "👋 هلا!\nابعتلي رابط من تيك توك / إنستغرام / بنترست / يوتيوب وأنا بحمّلك ياه."
    )


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if await is_subscribed(context, user_id):
        await query.edit_message_text("✅ تمام! هلأ ابعتلي الرابط يلي بدك ياه.")
    else:
        await query.edit_message_text(
            "❌ لسا ما اشتركت!\nاشترك بالقناة وبعدها اضغط (تحققت من الاشتراك).",
            reply_markup=subscribe_keyboard(),
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_subscribed(context, user_id):
        await update.message.reply_text(
            "🔒 لتستخدم البوت، لازم تكون مشترك بقناتنا أولاً:",
            reply_markup=subscribe_keyboard(),
        )
        return

    url = extract_url(update.message.text)
    if not url:
        await update.message.reply_text("❌ ما لقيت رابط بالرسالة.")
        return

    status = await update.message.reply_text("⏳ عم حمّل... استنى شوي")
    file_path = None
    try:
        file_path = await download_media(url)
        if not file_path or not os.path.exists(file_path):
            await status.edit_text("❌ فشل التحميل.")
            return

        if os.path.getsize(file_path) > 50 * 1024 * 1024:
            await status.edit_text("❌ الملف أكبر من 50 ميغا.")
            os.remove(file_path)
            return

        await status.edit_text("📤 عم ارفع...")
        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, 'rb') as f:
            if ext in ['.mp4', '.mov', '.mkv']:
                await update.message.reply_video(video=f, supports_streaming=True)
            elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
                await update.message.reply_photo(photo=f)
            else:
                await update.message.reply_document(document=f)

        os.remove(file_path)
        await status.delete()

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Private" in msg or "login" in msg.lower():
            await status.edit_text("🔒 المحتوى خاص أو يحتاج تسجيل دخول.")
        elif "Unsupported URL" in msg:
            await status.edit_text("❌ هالرابط غير مدعوم.")
        else:
            await status.edit_text(f"❌ خطأ: {msg[:200]}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logger.error(e)
        await status.edit_text("❌ صار خطأ غير متوقع.")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


# ---------------- التشغيل ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("🤖 البوت شغّال...")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main() 
