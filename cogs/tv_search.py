import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score

logger = logging.getLogger(__name__)

class TVSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tv", description="ابحث عن مسلسل 📺")
    @app_commands.describe(query="اسم المسلسل المُراد البحث عنه")
    async def search_tv_command(self, interaction: discord.Interaction, query: str):
        # 1. تأجيل الاستجابة
        await interaction.response.defer(thinking=True)
        logger.info("TV search requested | user_id=%s | query=%s", interaction.user.id, query)

        # 2. البحث عن المسلسل باستخدام دالة المسلسلات الجديدة
        results = await self.bot.services.tmdb.search_tv(query)
        if not results:
            await interaction.followup.send(f"❌ لم يتم العثور على أي مسلسل باسم: `{query}`")
            return

        # 3. ترتيب النتائج بخوارزمية الرانك واختيار الأفضل كافتراضي
        sorted_results = sorted(results, key=calculate_search_score, reverse=True)
        best_match = sorted_results[0]
        tv_id = best_match.get("id")

        # 4. جلب التفاصيل العميقة وحقنها في الـ Model
        tv = await self.bot.services.tmdb.get_tv_details(tv_id)
        if not tv:
            await interaction.followup.send("⚠️ حدث خطأ أثناء سحب تفاصيل المسلسل من السيرفر.")
            return

        # 5. إرسال الرسالة النصية المؤقتة (الهيكل الأساسي)
        await interaction.followup.send(f"✅ تم العثور بنجاح على: **{tv.name}**")

async def setup(bot):
    await bot.add_cog(TVSearch(bot))
