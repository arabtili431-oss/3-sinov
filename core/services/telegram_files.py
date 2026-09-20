"""Videolarni yopiq Telegram kanalida saqlash va MTProto orqali uzatish.

Nima uchun: videolar serverda ochiq turmaydi, bazada faqat `file_id` saqlanadi.
Foydalanuvchi videoni faqat bizning serverimiz orqali, qisqa muddatli
imzolangan havola bilan oladi. Bot tokeni hech qachon mijozga chiqmaydi.

DIQQAT — bu versiya rasmiy HTTP Bot API o'rniga Pyrogram (MTProto) orqali
ishlaydi. Bot tokeni bilan MTProto orqali ulanganda rasmiy Bot API'ning
HTTP qatlamidagi 50 MB (yuklash) / 20 MB (yuklab olish) chegaralari
qo'llanilmaydi — shu sababli alohida Local Bot API server (telegram-bot-api
binary) ishga tushirishga hojat qolmaydi. Botlar uchun amaliy chegara —
taxminan 2 GB.

Kerakli sozlamalar (.env):
    TELEGRAM_BOT_TOKEN       — @BotFather'dan
    TELEGRAM_API_ID          — https://my.telegram.org/apps dan
    TELEGRAM_API_HASH        — https://my.telegram.org/apps dan
    TELEGRAM_STORAGE_CHAT_ID — videolar saqlanadigan yopiq kanal

O'rnatish:  pip install pyrogram tgcrypto
"""
import asyncio
import io
import logging
import os
import queue
import threading
import traceback

from django.conf import settings

logger = logging.getLogger(__name__)

# Pyrogram `stream_media()` funksiyasi shu birlikda (chunk) offset/limit oladi.
CHUNK_SIZE = 1024 * 1024  # 1 MB

# Botlar uchun MTProto orqali amaliy yuklash/yuklab olish chegarasi (~2 GB).
MAX_FILE_SIZE = 2 * 1000 * 1024 * 1024

_SENTINEL = object()


class TelegramStorageError(Exception):
    """Telegram bilan ishlashda yuzaga kelgan xato."""


def is_configured() -> bool:
    return bool(
        settings.TELEGRAM_BOT_TOKEN
        and settings.TELEGRAM_STORAGE_CHAT_ID
        and settings.TELEGRAM_API_ID
        and settings.TELEGRAM_API_HASH
    )


def is_local_api() -> bool:
    """Eski nom — shablonlar bilan moslik uchun qoldirilgan.

    Endi doim False qaytaradi: Local Bot API server o'rniga to'g'ridan-to'g'ri
    MTProto (Pyrogram) orqali ulanamiz.
    """
    return False


def download_limit() -> int:
    return MAX_FILE_SIZE


# --------------------------------------------------------- Pyrogram runtime
class _Runtime:
    """Fon oqimida (background thread) ishlaydigan yagona asyncio loop + Pyrogram client.

    Django view'lari sinxron ishlagani uchun, har bir chaqiruvni shu loop'ga
    `run_coroutine_threadsafe` orqali yuboramiz va natijani kutib olamiz.
    Client va loop butun jarayon davomida bitta marta ishga tushiriladi
    (lazy — birinchi chaqiruvda).
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self.loop = None
        self.client = None
        self._boot_lock = threading.Lock()

    @classmethod
    def get(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def ensure_ready(self, timeout=30):
        if self.client is not None:
            return
        with self._boot_lock:
            if self.client is not None:
                return
            self._start_loop()
            self._start_client(timeout=timeout)

    def _start_loop(self):
        ready = threading.Event()
        boot_error = {}

        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            try:
                # Pyrogram'ni ANIQ shu yerda, birinchi marta import qilamiz.
                # Sabab: pyrogram/sync.py modul yuklanayotganda (import vaqtida)
                # `asyncio.get_event_loop()`ni chaqiradi. Agar birinchi import
                # asyncio loop o'rnatilmagan ipda (masalan, Django so'rov ipida)
                # sodir bo'lsa — xato chiqadi. Shu ipda esa loop allaqachon
                # `asyncio.set_event_loop(loop)` bilan o'rnatilgan, shuning
                # uchun import xavfsiz o'tadi. Keyingi importlar (boshqa
                # iplarda) esa Python modul keshidan (sys.modules) olinadi —
                # qayta ijro etilmaydi, muammo tug'dirmaydi.
                import pyrogram  # noqa: F401
            except Exception as exc:  # noqa: BLE001
                boot_error["exc"] = exc
            ready.set()
            loop.run_forever()

        threading.Thread(target=runner, name="telegram-mtproto", daemon=True).start()
        if not ready.wait(timeout=10):
            raise TelegramStorageError("Telegram uchun fon oqimi (event loop) ishga tushmadi.")
        if "exc" in boot_error:
            raise TelegramStorageError(
                f"Pyrogram'ni import qilib bo'lmadi: {boot_error['exc']}"
            ) from boot_error["exc"]

    def _start_client(self, timeout=30):
        try:
            from pyrogram import Client
        except ImportError as exc:
            raise TelegramStorageError(
                "Pyrogram o'rnatilmagan. Terminalda: pip install pyrogram tgcrypto"
            ) from exc

        session_dir = str(settings.TELEGRAM_SESSION_DIR)
        os.makedirs(session_dir, exist_ok=True)

        # DIQQAT: Client(...) obyekti ATAYIN shu yerda emas, fon loop ipida
        # (pastdagi _create_and_start ichida) yaratiladi. Pyrogram ba'zi ichki
        # obyektlarini konstruktorda `asyncio.get_event_loop()` bilan oladi —
        # buni to'g'ridan-to'g'ri (Django) so'rov ipida chaqirsak, o'sha ipda
        # asyncio loop o'rnatilmagani uchun "There is no current event loop in
        # thread ..." xatosi chiqadi. Konstruktorni ham fon loop ipida
        # bajarish shu muammoni butunlay oldini oladi.
        async def _create_and_start():
            client = Client(
                name="vector_storage_bot",
                api_id=int(settings.TELEGRAM_API_ID),
                api_hash=settings.TELEGRAM_API_HASH,
                bot_token=settings.TELEGRAM_BOT_TOKEN,
                workdir=session_dir,
            )
            await client.start()

            # Bot allaqachon kanalga admin qilib qo'shilgan bo'lsa ham, bu
            # YANGI Pyrogram (MTProto) sessiyasi o'sha kanalni hali "ko'rmagan"
            # bo'lishi mumkin — shu sabab PEER_ID_INVALID chiqadi. Taklif
            # havolasi orqali bir marta "join" qilib ko'rish orqali peer
            # keshlanadi. Agar allaqachon a'zo bo'lsa, xato e'tiborsiz
            # qoldiriladi (baribir keyingi urinish resolve_peer'ni sinaydi).
            invite = getattr(settings, "TELEGRAM_STORAGE_CHAT_INVITE", "")
            if invite:
                try:
                    await client.join_chat(invite)
                except Exception as exc:  # noqa: BLE001
                    logger.info(
                        "join_chat muvaffaqiyatsiz (odatda zararsiz, allaqachon a'zo bo'lishi mumkin): %s",
                        exc,
                    )

            return client

        fut = asyncio.run_coroutine_threadsafe(_create_and_start(), self.loop)
        try:
            self.client = fut.result(timeout=timeout)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Pyrogram client ishga tushmadi:\n%s", tb)
            raise TelegramStorageError(f"Telegram (MTProto) bilan ulanib bo'lmadi: {exc}\n\n{tb}") from exc

    def call(self, coro_fn, timeout=600):
        """`coro_fn(client)` — coroutine qaytaruvchi funksiyani fon loop'ida bajaradi."""
        self.ensure_ready()
        fut = asyncio.run_coroutine_threadsafe(coro_fn(self.client), self.loop)
        return fut.result(timeout=timeout)


def _runtime() -> _Runtime:
    return _Runtime.get()


def _chat_id():
    """TELEGRAM_STORAGE_CHAT_ID ni butun songa aylantirib qaytaradi.

    DIQQAT: `os.getenv()` har doim STRING qaytaradi. Agar shu qiymat
    Pyrogram'ga string holida uzatilsa, `resolve_peer()` uni telefon
    raqami sifatida talqin qilib, `contacts.ResolvePhone` orqali
    yechishga urinadi — bu botlar uchun taqiqlangan va
    `BOT_METHOD_INVALID` xatosini beradi. Shu sababli har doim
    aniq `int()`ga o'tkazamiz (xuddi test_telegram.py'da qilingandek).
    """
    return int(settings.TELEGRAM_STORAGE_CHAT_ID)


# -------------------------------------------------------------- Yuklash
def upload_video(file_obj, filename, caption="", duration=0):
    """Videoni yopiq kanalga yuklaydi va file_id qaytaradi.

    file_obj — ochiq fayl obyekti (masalan, request.FILES['video']).
    """
    if not is_configured():
        raise TelegramStorageError(
            "Telegram saqlash sozlanmagan: .env da TELEGRAM_API_ID, TELEGRAM_API_HASH, "
            "TELEGRAM_BOT_TOKEN va TELEGRAM_STORAGE_CHAT_ID to'ldirilganini tekshiring."
        )

    size = getattr(file_obj, "size", 0)
    if size and size > MAX_FILE_SIZE:
        raise TelegramStorageError(
            f"Fayl juda katta ({size / 1048576:.0f} MB). Bitta faylning maksimal hajmi — 2 GB."
        )

    file_obj.seek(0)
    buffer = io.BytesIO(file_obj.read())
    buffer.name = filename  # Pyrogram fayl nomi/kengaytmasini shundan aniqlaydi

    async def _upload(client):
        try:
            return await client.send_video(
                chat_id=_chat_id(),
                video=buffer,
                caption=caption[:1000],
                duration=int(duration) if duration else 0,
                supports_streaming=True,
                file_name=filename,
            )
        except Exception as exc:
            # Ba'zi formatlar video sifatida qabul qilinmaydi — hujjat sifatida yuboramiz
            logger.warning("send_video muvaffaqiyatsiz: %s. send_document bilan urinamiz.", exc)
            buffer.seek(0)
            return await client.send_document(
                chat_id=_chat_id(),
                document=buffer,
                caption=caption[:1000],
                file_name=filename,
            )

    try:
        message = _runtime().call(_upload)
    except TelegramStorageError:
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Video yuklashda kutilmagan xato:\n%s", tb)
        raise TelegramStorageError(f"Telegramga yuklab bo'lmadi: {exc}\n\n{tb}") from exc

    media = getattr(message, "video", None) or getattr(message, "document", None)
    if media is None:
        raise TelegramStorageError("Telegram javobida video/hujjat topilmadi.")

    return {
        "file_id": media.file_id,
        "message_id": getattr(message, "id", None) or getattr(message, "message_id", None),
        "size": getattr(media, "file_size", size) or size,
        "duration": getattr(media, "duration", duration) or duration,
        "mime_type": getattr(media, "mime_type", "") or "",
    }


def upload_document(file_obj, filename, caption=""):
    """Dars materialini (PDF va h.k.) kanalga yuklaydi."""
    if not is_configured():
        raise TelegramStorageError("Telegram saqlash sozlanmagan.")

    file_obj.seek(0)
    buffer = io.BytesIO(file_obj.read())
    buffer.name = filename

    async def _upload(client):
        return await client.send_document(
            chat_id=_chat_id(),
            document=buffer,
            caption=caption[:1000],
            file_name=filename,
        )

    try:
        message = _runtime().call(_upload)
    except TelegramStorageError:
        raise
    except Exception as exc:
        raise TelegramStorageError(f"Telegramga yuklab bo'lmadi: {exc}") from exc

    doc = getattr(message, "document", None)
    return {
        "file_id": doc.file_id if doc else "",
        "size": getattr(doc, "file_size", 0) if doc else 0,
        "message_id": getattr(message, "id", None) or getattr(message, "message_id", None),
    }


# --------------------------------------------------------------- Uzatish
def stream_file(file_id, chunk_size=CHUNK_SIZE, range_header=None, file_size=0):
    """Faylni Telegramdan MTProto orqali oqim (stream) ko'rinishida uzatadi.

    (generator, content_type, status, headers) qaytaradi — API eskisi bilan bir xil.
    `file_size` — bazada saqlangan `video_size` (Lesson.video_size) — aniq
    `Content-Range`/`Content-Length` hisoblash va videoni oldinga surish
    (seek) uchun kerak. Berilmasa, butun fayl 200 status bilan uzatiladi.

    DIQQAT: bu funksiya Pyrogram'ning `stream_media()` metodini "bo'lak"
    (1 MB) birligida offset/limit bilan chaqiradi — bu ko'plab ochiq
    manbali Telegram-striming loyihalarida qo'llaniladigan standart usul.
    Ishga tushirishdan oldin haqiqiy (>20 MB) video bilan qo'lda sinab
    ko'rish tavsiya etiladi.
    """
    rt = _runtime()
    rt.ensure_ready()

    start = 0
    end = (file_size - 1) if file_size else None
    status = 200
    resp_headers = {}

    if range_header and range_header.startswith("bytes="):
        try:
            rng = range_header.split("=", 1)[1]
            start_s, _, end_s = rng.partition("-")
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else end
        except ValueError:
            start, end = 0, (file_size - 1 if file_size else None)

        if file_size:
            end = min(end, file_size - 1) if end is not None else file_size - 1
            status = 206
            resp_headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            resp_headers["Content-Length"] = str(end - start + 1)

    offset_chunk = start // chunk_size
    first_cut = start % chunk_size
    if end is not None:
        part_count = (end // chunk_size) - offset_chunk + 1
        last_cut = (end % chunk_size) + 1
    else:
        part_count = 0  # 0 — Pyrogram uchun "oxirigacha" degani
        last_cut = None

    q: "queue.Queue" = queue.Queue(maxsize=8)

    async def _produce():
        loop = asyncio.get_event_loop()
        try:
            index = 0
            async for chunk in rt.client.stream_media(file_id, offset=offset_chunk, limit=part_count):
                index += 1
                piece = chunk
                if part_count == 1:
                    piece = piece[first_cut:last_cut]
                elif index == 1:
                    piece = piece[first_cut:]
                elif part_count and index == part_count:
                    piece = piece[:last_cut]
                # Navbatga qo'yishni alohida ipda bajaramiz — asosiy loop bloklanmasin
                await loop.run_in_executor(None, q.put, piece)
            await loop.run_in_executor(None, q.put, _SENTINEL)
        except Exception as exc:  # noqa: BLE001
            await loop.run_in_executor(None, q.put, exc)

    asyncio.run_coroutine_threadsafe(_produce(), rt.loop)

    def generate():
        while True:
            item = q.get()
            if item is _SENTINEL:
                break
            if isinstance(item, Exception):
                raise TelegramStorageError(f"Telegramdan oqim uzatishda xato: {item}") from item
            if item:
                yield item

    return generate(), "video/mp4", status, resp_headers


def delete_message(message_id):
    """Kanaldagi xabarni o'chiradi (dars o'chirilganda)."""
    if not is_configured() or not message_id:
        return False

    async def _delete(client):
        return await client.delete_messages(
            chat_id=_chat_id(), message_ids=message_id,
        )

    try:
        return bool(_runtime().call(_delete, timeout=30))
    except Exception as exc:
        logger.warning("Xabarni o'chirib bo'lmadi: %s", exc)
        return False
