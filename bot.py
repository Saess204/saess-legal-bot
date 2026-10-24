import os
import requests
import asyncio
import base64
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from pypdf import PdfReader

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8908467332:AAHC_ALFUDvLtdElZi6_lMm6ppA5CvjMWmA")
# استفاده از کلید جدید و معتبر شما
OPENAI_API_KEY = "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"

app = Flask(__name__)

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

LEGAL_SYSTEM_PROMPT = """
تو یک وکیل پایه یک دادگستری، مشاور حقوقی زبده و دستیار هوشمند به نام "Saess" هستی.
وظیفه تو ارائه مشاوره تخصصی، تحلیل عمیق مدارک، تشخیص استراتژی‌های دفاعی و ارائه راهکارهای عملی حقوقی بر اساس قوانین جاری ایران (آیین دادرسی مدنی، کیفری، قانون مدنی، مجازات اسلامی و تجارت) است.

هنگام پاسخگویی به کاربر نکات زیر را رعایت کن:
۱. مانند یک وکیل با تجربه و تحلیل‌گر فکر کن؛ ابهامات پرونده را مشخص کن و نقاط ضعف و قوت طرفین را تحلیل نما.
۲. مواد قانونی مرتبط و استدلال‌های حقوقی محکم ارائه بده.
۳. راهکارهای گام‌به‌گام و عملی (نحوه تنظیم دادخواست، لایحه، اظهارنامه یا اقدامات پیشگیرانه) پیشنهاد بده.
۴. لحن گفتگو باید کاملاً محترمانه، تخصصی، اطمینان‌بخش و روان باشد.
۵. اگر عکس سند یا فایل PDF ارسال شد، تمام جزئیات متن، شروط قرارداد و مفاد آن را با دقت آنالیز کن.
"""

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def ask_legal_ai(messages_list):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY.strip()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o",
        "messages": messages_list,
        "temperature": 0.3,
        "max_tokens": 2500
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return f"⚠️ خطای OpenAI (کد {response.status_code}):\n{response.text}"
    except Exception as e:
        return f"⚠️ خطای ارتباطی: {str(e)}"

async def start_command(update: Update, context):
    await update.message.reply_text(
        "سلام و احترام.\nمن **Saess** هستم؛ وکیل و مشاور حقوقی هوشمند شما.\n\n"
        "می‌توانید سوالات حقوقی خود را بپرسید، متن قراردادها را ارسال کنید، یا **تصویر مدارک و فایل‌های PDF** پرونده را بفرستید تا آن‌ها را آنالیز کرده و راهکار قانونی ارائه دهم."
    )

async def handle_incoming_message(update: Update, context):
    message = update.message
    text = message.text or message.caption or ""
    messages_payload = [{"role": "system", "content": LEGAL_SYSTEM_PROMPT}]
    
    if message.document and message.document.file_name.lower().endswith('.pdf'):
        await message.reply_text("📥 در حال دریافت، مطالعه و استخراج متن سند PDF...")
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
            
            prompt_content = f"محتوای کامل سند PDF ارسالی کاربر جهت بررسی و تحلیل حقوقی:\n\n{extracted}\n\nتوضیحات/سوال کاربر: {text}"
            messages_payload.append({"role": "user", "content": prompt_content})
            
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            await message.reply_text(f"⚠️ خطا در استخراج متن PDF: {e}")
            return

    elif message.photo:
        await message.reply_text("🔍 در حال آنالیز تصویری سند/مدرک حقوقی ارسالی...")
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        path = f"temp_{photo.file_id}.jpg"
        await file.download_to_drive(path)
        
        try:
            base64_image = encode_image(path)
            user_prompt = text if text else "لطفاً این تصویر/سند حقوقی را کاملاً آنالیز کن، مفاد آن را استخراج کرده و تحلیل حقوقی ارائه بده."
            
            messages_payload.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            })
            
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            await message.reply_text(f"⚠️ خطا در پردازش تصویر: {e}")
            return

    else:
        if not text.strip():
            text = "سلام، لطفاً خودتان را معرفی کنید و بگویید چه کمک حقوقی می‌توانید بکنید."
        messages_payload.append({"role": "user", "content": text})

    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    ai_analysis = ask_legal_ai(messages_payload)
    await message.reply_text(ai_analysis)

telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_incoming_message))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(telegram_app.initialize())

@app.route("/")
def index():
    return "Saess Legal AI Consultant is Active & Live!"

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
