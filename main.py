# main.py
from keep_alive import keep_alive
import discord
from discord.ext import commands
import os
import logging
from config.settings import settings
from services.database_service import DatabaseService
from services.tmdb_service import TMDBService
from services.service_container import ServiceContainer

# تفعيل الـ Logging بالتنسيق الاحترافي الجديد لمنع الفوضى في الـ Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

class OdinnBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # تم إيقاف intents.members لتوفير الموارد وتقليل استهلاك الـ RAM على Render Free
        super().__init__(command_prefix="!", intents=intents)
        
        # إنشاء الخدمات وحقنها في الـ Container المحدث بالـ Type Hints الكاملة
        self.db_service = DatabaseService()
        self.tmdb_service = TMDBService()
        self.services = ServiceContainer(self.tmdb_service, self.db_service)

    async def setup_hook(self):
        """تهيئة البوت: فتح الاتصالات وتحميل الكوجز بأمان مع مزامنة الـ Slash Commands تلقائياً"""
        # تهيئة TMDB فقط (قاعدة بيانات Supabase تقوم بالاتصال فوراً في __init__)
        await self.tmdb_service.initialize()
        
        # تحميل كل ملفات الكوجز أوتوماتيكياً
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f'⚙️ Loaded Cog: {filename}')
                except Exception as e:
                    logger.error(f'❌ Failed to load Cog {filename}: {e}')

        # مزامنة أوامر الـ Slash مع سيرفرات Discord أوتوماتيكياً عند الإقلاع
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} slash command(s).")
        except Exception as e:
            logger.error(f"❌ Failed to sync slash commands: {e}")

    async def close(self):
        """الإغلاق الآمن للبوت والتنظيف وراءه (Graceful Shutdown)"""
        logger.info("🛑 Shutting down Odinn Bot safely...")
        await self.tmdb_service.close()
        await super().close()

bot = OdinnBot()

# أمر مزامنة أوامر السلاش اليدوي (كأداة احتياطية للمطور حماية من الـ Rate Limit)
@bot.command()
@commands.is_owner()
@commands.guild_only()
async def sync(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"🔄 Synced {len(synced)} slash command(s) successfully.")
        logger.info(f"🔄 Synced {len(synced)} commands via Developer Command.")
    except Exception as e:
        await ctx.send(f"❌ Error syncing commands: {e}")
        logger.error(f"Error syncing commands: {e}")

@bot.event
async def on_ready():
    logger.info(f'✅ Logged in successfully as {bot.user.name}')
    logger.info('⚔️ Odinn Bot V2 Enterprise Architecture is online!')
    
    # --- منطقة اختبار الـ Supabase (تُحذف بالكامل بعد التأكد من نجاحها) ---
    logger.info("="*40)
    logger.info("🚀 بدء اختبارات قاعدة البيانات...")
    
    db = bot.services.db  
    
    # 0. اختبار الاتصال
    is_connected = await db.test_connection()
    logger.info("Connection Test: %s", is_connected)
    
    if is_connected:
        # 1. اختبار الإضافة (Add)
        added = await db.add_to_watchlist(
            user_id=1,
            tmdb_id=123,
            media_type="movie",
            media_name="Interstellar",
            poster_url="https://example.com/poster.jpg",
            release_year="2014"
        )
        logger.info("Add Test: %s", added)
        
        # 2. اختبار التحقق (Check)
        is_in = await db.is_in_watchlist(user_id=1, tmdb_id=123, media_type="movie")
        logger.info("Check Test: %s", is_in)
        
        # 3. اختبار العد (Count)
        count_all = await db.count_watchlist_items(user_id=1)
        logger.info("Count Test: %s", count_all)
        
        # 4. اختبار الجلب (Get)
        watchlist = await db.get_watchlist(user_id=1)
        first_item = watchlist[0].get('media_name') if watchlist else 'None'
        logger.info("Get Test: Retrieved %s items. First item: %s", len(watchlist), first_item)

    logger.info("="*40)
    # -------------------------------------------------------------------------

if __name__ == "__main__":
    keep_alive()
    bot.run(settings.DISCORD_TOKEN)
