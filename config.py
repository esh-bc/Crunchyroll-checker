"""
CrunchyBot – Central Configuration
All hardcoded secrets and tunables live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ═══════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "@CrunchyCheckerBot")
DEV_CREDIT: str = os.getenv("DEV_CREDIT", "@iam_eshh")

ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

REQUIRED_CHANNELS: list[str] = [
    ch.strip()
    for ch in os.getenv("REQUIRED_CHANNELS", "").split(",")
    if ch.strip()
]

# ═══════════════════════════════════════════
# MONGODB
# ═══════════════════════════════════════════
MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "crunchybot")

# ═══════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════
HEALTH_PORT: int = int(os.getenv("HEALTH_PORT", "8080"))

# ═══════════════════════════════════════════
# CHECKER ENGINE
# ═══════════════════════════════════════════
MAX_CONCURRENT: int = int(os.getenv("MAX_CONCURRENT", "100"))
MAX_CONCURRENT_PER_USER: int = int(os.getenv("MAX_CONCURRENT_PER_USER", "10"))
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "25"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
RATE_LIMIT_DELAY: float = float(os.getenv("RATE_LIMIT_DELAY", "0.3"))

# ═══════════════════════════════════════════
# FILE LIMITS
# ═══════════════════════════════════════════
MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(5 * 1024 * 1024)))  # 5 MB
MAX_COMBO_FREE: int = int(os.getenv("MAX_COMBO_PER_SESSION_FREE", "10000"))
MAX_COMBO_PREMIUM: int = int(os.getenv("MAX_COMBO_PER_SESSION_PREMIUM", "100000"))

# ═══════════════════════════════════════════
# PROXY
# ═══════════════════════════════════════════
PROXY_TEST_URL: str = os.getenv("PROXY_TEST_URL", "https://beta-api.crunchyroll.com")
PROXY_TEST_TIMEOUT: int = int(os.getenv("PROXY_TEST_TIMEOUT", "10"))
MAX_PROXY_TEST_CONCURRENT: int = int(os.getenv("MAX_PROXY_TEST_CONCURRENT", "50"))

# ═══════════════════════════════════════════
# CRUNCHYROLL API
# ═══════════════════════════════════════════
BRN_API = "https://beta-api.crunchyroll.com"
BRN_CID = "rjs0ltx0dbwkliwxdzdf"
BRN_SEC = "4V7rf21-UFXeZ-5XAd0X_QPwr1gu_i1s"

PLAN_MAP = {"1": "FAN", "4": "MEGA FAN", "6": "ULTIMATE FAN"}

USER_AGENTS = [
    "Crunchyroll/ANDROIDTV/3.65.0_22347 (Android 10; en-US; sdk_google_atv_x86)",
    "Crunchyroll/ANDROIDTV/3.64.0_22200 (Android 11; en-US; sdk_google_atv_x86)",
    "Crunchyroll/ANDROIDTV/3.63.0_22000 (Android 12; en-US; sdk_google_atv_x86)",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
]

COUNTRY_MAP = {
    "US": "United States", "GB": "United Kingdom", "DE": "Germany", "FR": "France",
    "ES": "Spain", "IT": "Italy", "TR": "Turkey", "BR": "Brazil", "JP": "Japan",
    "KR": "South Korea", "IN": "India", "CA": "Canada", "AU": "Australia", "MX": "Mexico",
    "NL": "Netherlands", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
    "PL": "Poland", "RU": "Russia", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "PE": "Peru", "AE": "UAE", "SA": "Saudi Arabia", "EG": "Egypt", "ZA": "South Africa",
    "ID": "Indonesia", "MY": "Malaysia", "SG": "Singapore", "TH": "Thailand", "VN": "Vietnam",
    "PH": "Philippines", "KE": "Kenya", "NG": "Nigeria", "GH": "Ghana", "PT": "Portugal",
    "RO": "Romania", "HU": "Hungary", "CZ": "Czech Republic", "UA": "Ukraine",
    "AT": "Austria", "CH": "Switzerland", "BE": "Belgium", "IL": "Israel", "TW": "Taiwan",
    "HK": "Hong Kong", "PK": "Pakistan", "NZ": "New Zealand", "SK": "Slovakia",
    "HR": "Croatia", "RS": "Serbia", "BG": "Bulgaria", "LT": "Lithuania", "LV": "Latvia",
    "EE": "Estonia", "SI": "Slovenia", "IS": "Iceland", "LU": "Luxembourg",
    "IE": "Ireland", "CY": "Cyprus", "MT": "Malta", "CR": "Costa Rica",
    "PA": "Panama", "DO": "Dominican Republic", "GT": "Guatemala", "EC": "Ecuador",
    "UY": "Uruguay", "PY": "Paraguay", "BO": "Bolivia", "SV": "El Salvador",
    "HN": "Honduras", "NI": "Nicaragua", "CU": "Cuba", "JM": "Jamaica",
    "TT": "Trinidad and Tobago", "BB": "Barbados", "BH": "Bahrain", "OM": "Oman",
    "KW": "Kuwait", "QA": "Qatar", "BD": "Bangladesh", "LK": "Sri Lanka",
    "NP": "Nepal", "MM": "Myanmar", "KH": "Cambodia", "LA": "Laos",
    "MN": "Mongolia", "AL": "Albania", "MK": "North Macedonia", "ME": "Montenegro",
    "BA": "Bosnia and Herzegovina", "XK": "Kosovo", "MD": "Moldova",
    "BY": "Belarus", "GE": "Georgia", "AM": "Armenia", "AZ": "Azerbaijan",
    "KZ": "Kazakhstan", "UZ": "Uzbekistan", "TM": "Turkmenistan", "KG": "Kyrgyzstan",
    "TJ": "Tajikistan", "IQ": "Iraq", "IR": "Iran", "SY": "Syria",
    "JO": "Jordan", "LB": "Lebanon", "PS": "Palestine", "YE": "Yemen",
    "DZ": "Algeria", "TN": "Tunisia", "MA": "Morocco", "LY": "Libya",
    "SD": "Sudan", "ET": "Ethiopia", "TZ": "Tanzania", "UG": "Uganda",
    "RW": "Rwanda", "CD": "DR Congo", "CM": "Cameroon", "SN": "Senegal",
    "CI": "Ivory Coast", "ML": "Mali", "BF": "Burkina Faso", "NE": "Niger",
    "TG": "Togo", "BJ": "Benin", "GN": "Guinea", "MG": "Madagascar",
    "MU": "Mauritius", "SC": "Seychelles",
}

# ═══════════════════════════════════════════
# PLAN DEFINITIONS
# ═══════════════════════════════════════════
PLANS = {
    "free": {
        "label": "Fʀᴇᴇ",
        "max_combo": MAX_COMBO_FREE,
        "max_concurrent_jobs": 1,
        "speed_limit": 50,          # max concurrent per job
    },
    "premium": {
        "label": "Pʀᴇᴍɪᴜᴍ",
        "max_combo": MAX_COMBO_PREMIUM,
        "max_concurrent_jobs": 2,
        "speed_limit": 100,         # max concurrent per job
    },
}

# ═══════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════
BASE_DIR = Path(__file__).parent
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)
