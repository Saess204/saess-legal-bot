import os
import requests
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from pypdf import PdfReader

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8908467332:AAHC_ALFUDvLtdElZi6_lMm6ppA5CvjMWmA")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCO9ScNq3PJ61BO_W-k-dF1A634oibn_ds")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "") # اگر کلید دیپ سیک دارید اینجا بگذارید

app = Flask(__name__)

# ساخت امن اپلیکیشن تلگرام بدون خطای Updater
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

def ask_gemini(prompt):
    """تلاش اول: ارسال درخواست به گوگل جمینای"""
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("AIzaSyCO9ScN"):
        return None # اگر کلید معتبر نیست رد شو
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            return f"{text}\n\n🤖 **مدل پاسخگو:** Google Gemini"
    except Exception as e:
        print(f"Gemini Error: {e}")
    return None

def ask_openai(prompt):
    """تلاش دوم: اگر جمینای پاسخ نداد، استفاده از ChatGPT"""
    if not OPENAI_API_KEY:
        return None
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "تو یک مشاور و دستیار هوشمند حقوقی متبحر به نام Saess هستی که به زبان فارسی پاسخ می‌دهد."},
            {"role": "user", "content": prompt[:4000]}
        ],
        "temperature": 0.5
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            text = data['choices'][0]['message']['content']
            return f"{text}\n\n🤖 **مدل پاسخگو:** OpenAI GPT-4o-mini"
    except Exception as e:
        print(f"OpenAI Error: {e}")
    return None

def ask_deepseek(prompt):
    """تلاش سوم: اگر جی‌پتی هم نبود، استفاده از DeepSeek"""
    if not DEEPSEEK_API_KEY:
        return None
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "تو یک مشاور حقوقی هوشمند به نام Saess هستی."},
            {"role": "user", "content": prompt[:4000]}
        ]
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            text = data['choices'][0]['message']['content']
            return f"{text}\n\n🤖 **مدل پاسخگو:** DeepSeek"
    except Exception as e:
        print(f"DeepSeek Error: {e}")
    return None

def get_ai_response_chain(prompt):
    """مدیریت هوشمند زنجیره: اول جمینای -> دوم چت‌جی‌پتی -> سوم دیپ‌سیک"""
    print("در حال بررسی اتصال به Google Gemini...")
    ans = ask_gemini(prompt)
    if ans:
        return ans

    print("جمینای پاسخ نداد. در حال انتقال به OpenAI...")
    ans = ask_openai(prompt)
    if ans:
        return ans

    print("OpenAI پاسخ نداد. در حال انتقال به DeepSeek...")
    ans = ask_deepseek(prompt)
    if ans:
        return ans

    return "⚠️ متأسفانه در حال حاضر هیچ‌کدام از مدل‌های هوش مصنوعی (جمینای، چت‌جی‌پتی و دیپ‌سیک) در دسترس نیستند. لطفاً دقایقی دیگر تلاش کنید."

async def start_command(update: Update, context):
    await update.message.reply_text("سلام! من **Saess** هستم؛ دستیار حقوقی هوشمند شما مجهز به سیستم چندگانه (Gemini / OpenAI / DeepSeek). سوال یا فایل PDF خود را بفرستید.")

async def handle_incoming_message(update: Update, context):
    message = update.message
    text = message.text or message.caption or ""
    
    if message.document and message.document.file_name.lower().endswith('.pdf'):
        await message.reply_text("📥 در حال خواندن متن فایل PDF...")
        file = await context.bot.get_file(message.document.file_id)
        path = f"temp_{message.document.file_name}"
        await file.download_to_drive(path)
        try:
            reader = PdfReader(path)
            extracted = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    extracted += t + "\n"
            text = f"محتوای فایل PDF ارسالی:\n{extracted}" if extracted else "[فایل PDF خالی]"
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            text = f"[خطا در خواندن PDF: {e}]"

    if not text.strip():
        text = "سلام، لطفاً راهنمایی‌ام کنید."

    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    
    # دریافت پاسخ از زنجیره هوش مصنوعی
    ai_reply = get_ai_response_chain(text)
    
    await message.reply_text(ai_reply)

telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_incoming_message))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(telegram_app.initialize())

@app.route("/")
def index():
    return "Saess Multi-AI Legal Bot is active!"

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, telegram_app.bot)
    loop.run_until_complete(telegram_app.process_update(update))
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    webhook_url = f"https://saess-legal-bot.onrender.com/{TELEGRAM_BOT_TOKEN}"
    loop.run_until_complete(telegram_app.bot.set_webhook(url=webhook_url))
    app.run(host="0.0.0.0", port=port)
