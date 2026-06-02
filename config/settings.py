from dataclasses import dataclass
import os
import logging

logger = logging.getLogger(__name__)

# محاولة تحميل dotenv لو شغالين محلياً، وتجاهلها لو على Render
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@dataclass(frozen=True)
class Settings:
    DISCORD_TOKEN: str
    TMDB_API_KEY: str
    MOVIES_CHANNEL_ID: int
    DB_PATH: str

    def __post_init__(self):
        """Fail-Fast Validation: التأكد من وجود كل المتغيرات الأساسية قبل تشغيل البوت"""
        if not self.DISCORD_TOKEN:
            raise ValueError("🚨 DISCORD_TOKEN is missing from environment variables!")
        if not self.TMDB_API_KEY:
            raise ValueError("🚨 TMDB_API_KEY is missing from environment variables!")
        if self.MOVIES_CHANNEL_ID <= 0:
            raise ValueError("🚨 MOVIES_CHANNEL_ID is invalid! Must be a positive integer.")

# أوبجكت جاهز للاستخدام في أي مكان في المشروع
settings = Settings(
    DISCORD_TOKEN=os.getenv("DISCORD_TOKEN", ""),
    TMDB_API_KEY=os.getenv("TMDB_API_KEY", ""),
    MOVIES_CHANNEL_ID=int(os.getenv("MOVIES_CHANNEL_ID", 1510778860982108420)),
    DB_PATH=os.getenv("DB_PATH", "database/movies_history.db")
)
