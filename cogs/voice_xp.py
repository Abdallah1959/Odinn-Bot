import discord
from discord.ext import commands, tasks
from database.db_manager import add_xp, get_user, update_level

class VoiceXP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # ==========================================
        # ⚙️ الإعدادات الأساسية للصوت (تعديل الـ IDs)
        # ==========================================
        self.xp_per_minute = 10  
        self.level_up_channel_id = 1510680410961739967  # نفس ID روم التهنئة

        self.voice_tracker.start()

    def cog_unload(self):
        self.voice_tracker.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("🎙️ Voice XP Cog is ready with Real-Time tracking!")

    # حلقة دورية حقيقية تدور كل دقيقة كاملة لمنح النقاط لايف
    @tasks.loop(minutes=1.0)
    async def voice_tracker(self):
        for guild in self.bot.guilds:
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if member.bot:
                        continue

                    guild_id = guild.id
                    add_xp(member.id, guild_id, self.xp_per_minute)

                    user_data = get_user(member.id, guild_id)
                    if user_data:
                        current_xp, current_level = user_data
                        xp_needed = (current_level + 1) * 100

                        if current_xp >= xp_needed:
                            new_level = current_level + 1
                            update_level(member.id, guild_id, new_level)

                            channel = self.bot.get_channel(self.level_up_channel_id)
                            if channel:
                                embed = discord.Embed(
                                    title="🎙️ ارتقاء في التصنيف الصوتي!",
                                    description=f"الأسطورة {member.mention} مستمر في التفاعل الصوتي ووصل للمستوى **{new_level}** ⚔️",
                                    color=discord.Color.blue()
                                )
                                if member.display_avatar:
                                    embed.set_thumbnail(url=member.display_avatar.url)
                                await channel.send(content=f"{member.mention}", embed=embed)

    @voice_tracker.before_loop
    async def before_voice_tracker(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(VoiceXP(bot))