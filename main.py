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
        """تهيئة البوت: فتح الاتصالات وتحميل الكوجز بأمان"""
        # تشغيل الخدمات وفتح الـ Connections مرة واحدة بس عند الإقلاع
        await self.db_service.initialize()
        await self.tmdb_service.initialize()
        
        # تحميل كل ملفات الكوجز أوتوماتيكياً
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f'⚙️ Loaded Cog: {filename}')
                except Exception as e:
                    logger.error(f'❌ Failed to load Cog {filename}: {e}')

    async def close(self):
        """الإغلاق الآمن للبوت والتنظيف وراءه (Graceful Shutdown)"""
        logger.info("🛑 Shutting down Odinn Bot safely...")
        await self.db_service.close()
        await self.tmdb_service.close()
        await super().close()

bot = OdinnBot()

# أمر مزامنة أوامر السلاش (للمطور فقط وداخل السيرفرات فقط حماية من الـ Rate Limit)
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
    print('⚔️ Odinn Bot V2 Enterprise Architecture is online!')

if __name__ == '__main__':
    # [تم التعديل]: التشغيل المباشر والآمن دون استدعاء أي ميزات خارجية مجهولة
    bot.run(settings.DISCORD_TOKEN)
