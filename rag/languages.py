"""Quốc gia gợi ý ngôn ngữ; người dùng luôn có thể chọn ngôn ngữ khác."""

from rag.errors import InvalidInput

LANGUAGES = {
    "vi": "Tiếng Việt / Vietnamese", "en": "English", "fr": "Français / French",
    "de": "Deutsch / German", "es": "Español / Spanish", "pt": "Português / Portuguese",
    "it": "Italiano / Italian", "nl": "Nederlands / Dutch", "ru": "Русский / Russian",
    "uk": "Українська / Ukrainian", "ja": "日本語 / Japanese", "ko": "한국어 / Korean",
    "zh-CN": "中文（简体）/ Chinese Simplified", "zh-TW": "中文（繁體）/ Chinese Traditional",
    "th": "ไทย / Thai", "id": "Bahasa Indonesia", "tr": "Türkçe / Turkish",
    "ar": "العربية / Arabic", "hi": "हिन्दी / Hindi",
}
COUNTRIES = {
    "Việt Nam / Vietnam": "vi", "Hoa Kỳ / United States": "en",
    "Vương quốc Anh / United Kingdom": "en", "Úc / Australia": "en",
    "Canada": "en", "Pháp / France": "fr", "Đức / Germany": "de",
    "Tây Ban Nha / Spain": "es", "Brazil": "pt", "Bồ Đào Nha / Portugal": "pt",
    "Ý / Italy": "it", "Hà Lan / Netherlands": "nl", "Nga / Russia": "ru",
    "Ukraine": "uk", "Nhật Bản / Japan": "ja", "Hàn Quốc / South Korea": "ko",
    "Trung Quốc / China": "zh-CN", "Đài Loan / Taiwan": "zh-TW",
    "Thái Lan / Thailand": "th", "Indonesia": "id", "Thổ Nhĩ Kỳ / Türkiye": "tr",
    "Ả Rập Xê Út / Saudi Arabia": "ar", "Ấn Độ / India": "hi",
}
PROVIDERS = {"groq": "Groq · dịch theo ngữ cảnh", "google": "Google Cloud Translation · API chính thức"}


def validate_language(code: str, *, allow_auto: bool = False) -> str:
    if code not in LANGUAGES and not (allow_auto and code == "auto"):
        raise InvalidInput(f"Ngôn ngữ không được hỗ trợ: {code}")
    return code


def ocr_codes(source_language: str) -> tuple[str, ...]:
    validate_language(source_language, allow_auto=True)
    if source_language == "auto":
        return ("vi", "en")
    code = {"zh-CN": "ch_sim", "zh-TW": "ch_tra"}.get(source_language, source_language)
    return ("en",) if code == "en" else (code, "en")
