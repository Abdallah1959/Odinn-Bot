import aiosqlite
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.db_path = settings.DB_PATH
        self.connection = None

    async def initialize(self):
        """فتح الاتصال مرة واحدة فقط عند بدء تشغيل البوت"""
        self.connection = await aiosqlite.connect(self.db_path)
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS posted_media (
                media_key TEXT PRIMARY KEY
            )
        ''')
        await self.connection.commit()
        logger.info("Database initialized successfully with a single connection.")

    async def is_posted(self, media_key: str) -> bool:
        if not self.connection: 
            return False
        async with self.connection.execute('SELECT 1 FROM posted_media WHERE media_key = ?', (media_key,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

    async def mark_as_posted(self, media_key: str):
        if self.connection:
            await self.connection.execute('INSERT INTO posted_media (media_key) VALUES (?)', (media_key,))
            await self.connection.commit()

    async def close(self):
        """إغلاق الاتصال بأمان وتصفير المتغير لتجنب أي أخطاء مستقبلية"""
        if self.connection:
            await self.connection.close()
            self.connection = None  # التلميعة الأخيرة بتاعت المهندس
            logger.info("Database connection closed safely.")
