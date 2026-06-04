import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class Watchlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="watchlist", description="View your personal watchlist 🍿")
    async def show_watchlist(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = interaction.user.id
        logger.info("Watchlist requested | user_id=%s", user_id)

        try:
            # 1. جلب البيانات من قاعدة البيانات باستعلام واحد فقط
            watchlist_items = await self.bot.services.db.get_watchlist(user_id)
            if not watchlist_items:
                await interaction.followup.send(
                    "🎬 Your watchlist is currently empty! Use `/movie` or `/tv` and click the add button to start building it. 🍿", 
                    ephemeral=True
                )
                return

            # 2. [In-Memory Optimization]: حساب الإحصائيات محلياً لسرعة فائقة
            total_items = len(watchlist_items)
            movies_count = sum(1 for item in watchlist_items if item.get("media_type") == "movie")
            tv_count = total_items - movies_count

            # 3. بناء قائمة النصوص بأفضل أداء (O(N) Time Complexity)
            lines = []
            for item in watchlist_items[:10]:
                media_type = item.get("media_type", "movie")
                media_name = item.get("media_name", "Unknown")
                release_year = item.get("release_year", "N/A")
                emoji = "🎬" if media_type == "movie" else "📺"
                lines.append(f"{emoji} **{media_name}** ({release_year})")

            # تلميح للمستخدم لو القائمة تتخطى 10 عناصر
            if total_items > 10:
                lines.append(f"")
                lines.append(f"*And {total_items - 10} more items... (Pagination coming soon) 🚀*")

            watchlist_text = "\n".join(lines)

            # 4. بناء الـ Embed باللغة الإنجليزية المتفق عليها
            embed = discord.Embed(
                title=f"📋 {interaction.user.display_name}'s Watchlist",
                description=watchlist_text,
                color=discord.Color.from_rgb(229, 9, 20)
            )
            embed.set_author(name="Odinn Cinema Network", icon_url=interaction.user.display_avatar.url)
            
            embed.add_field(
                name="📊 Watchlist Statistics",
                value=(
                    f"🎬 Movies: **{movies_count}**\n"
                    f"📺 TV Shows: **{tv_count}**\n"
                    f"📦 Total Items: **{total_items}**"
                ),
                inline=False
            )
            embed.set_footer(text=f"{total_items} items • Sorted by newest additions 🍿")

            await interaction.followup.send(embed=embed)

        # التعديل الجديد والمحسن لـ Render:
        except Exception:
            logger.exception("Error retrieving watchlist for user_id=%s", user_id)
            await interaction.followup.send("❌ An unexpected error occurred while retrieving your watchlist.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Watchlist(bot))
