"""Pyrogram ulanishini alohida, oddiy skript sifatida sinash.

Ishlatish (loyiha papkasida, venv faollashtirilgan holda):
    python test_telegram.py

Bu Django serverisiz, to'g'ridan-to'g'ri terminaldan ishlaydi — shuning uchun
bizning fon-oqim (background thread) murakkabligi bu yerda umuman yo'q va
muammoni Pyrogram/Telegram darajasida sodda tekshirish mumkin.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

API_ID = os.getenv("TELEGRAM_API_ID", "")
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_STORAGE_CHAT_ID", "")
INVITE = os.getenv("TELEGRAM_STORAGE_CHAT_INVITE", "")

print("=== Sozlamalar ===")
print("API_ID:   ", API_ID or "(BO'SH!)")
print("API_HASH: ", (API_HASH[:6] + "...") if API_HASH else "(BO'SH!)")
print("BOT_TOKEN:", (BOT_TOKEN[:10] + "...") if BOT_TOKEN else "(BO'SH!)")
print("CHAT_ID:  ", CHAT_ID or "(BO'SH!)")
print("INVITE:   ", INVITE or "(BO'SH — join_chat sinalmaydi)")
print()

if not (API_ID and API_HASH and BOT_TOKEN and CHAT_ID):
    raise SystemExit("Sozlamalar to'liq emas — .env faylini tekshiring.")

from pyrogram import Client  # noqa: E402

session_dir = str(BASE_DIR / "telegram_sessions")
os.makedirs(session_dir, exist_ok=True)

app = Client(
    name="vector_storage_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=session_dir,
)

with app:
    me = app.get_me()
    print("=== Bot ma'lumoti ===")
    print(f"Bot: @{me.username} (id={me.id})")
    print()

    if INVITE:
        print("=== join_chat sinovi ===")
        try:
            chat = app.join_chat(INVITE)
            print("MUVAFFAQIYATLI qo'shildi/allaqachon a'zo:", chat.id, chat.title)
        except Exception as exc:
            print("join_chat XATO (ko'pincha zararsiz, pastga qarang):", repr(exc))
        print()

    print("=== get_chat sinovi (raqamli ID bilan) ===")
    try:
        chat_id_int = int(CHAT_ID)
        chat = app.get_chat(chat_id_int)
        print("MUVAFFAQIYATLI topildi:", chat.id, chat.title)
    except Exception as exc:
        print("get_chat XATO:", repr(exc))
    print()

    print("=== Oddiy matnli xabar yuborish sinovi ===")
    try:
        msg = app.send_message(chat_id_int, "✅ Test xabar — Pyrogram orqali yuborildi.")
        print("MUVAFFAQIYATLI yuborildi! message_id =", msg.id)
    except Exception as exc:
        print("send_message XATO:", repr(exc))

print()
print("Tugadi.")
