import locale
from utils.libs.de import DE_KEYCODE_MAP

def detect_keyboard_layout():
    lang = locale.getdefaultlocale()[0]
    if lang.startswith("de"):
        return "de"
    elif lang.startswith("en"):
        return "us"
    return "unknown"


def map_to_de(key):
    """
    Mappt einen deutschen Sonderzeichen-Key auf die US-Tastenbelegung.
    Gibt den Original-Key zurück, wenn kein Mapping vorhanden ist.
    """
    return DE_KEYCODE_MAP.get(key, key)