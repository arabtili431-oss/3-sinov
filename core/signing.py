"""Video havolalarini imzolash — havola qisqa muddat va faqat bitta
foydalanuvchi uchun amal qiladi."""
from django.conf import settings
from django.core import signing

SALT = "vector.video"


def make_video_token(lesson_id, user_id):
    return signing.dumps({"l": int(lesson_id), "u": int(user_id or 0)}, salt=SALT)


def read_video_token(token, max_age=None):
    """Token to'g'ri bo'lsa (lesson_id, user_id) qaytaradi, aks holda None."""
    max_age = max_age if max_age is not None else settings.VIDEO_LINK_TTL
    try:
        data = signing.loads(token, salt=SALT, max_age=max_age)
        return int(data["l"]), int(data["u"])
    except (signing.BadSignature, signing.SignatureExpired, KeyError, ValueError, TypeError):
        return None
