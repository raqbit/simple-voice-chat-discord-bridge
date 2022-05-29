import discord.client
from discord import slash_command, ApplicationContext, option, VoiceClient


class VoiceBridgeCog(discord.Cog):
    @slash_command(name="join", description="Makes the bot join the given voice chat", guild_ids=['272461623241736193'])
    @option("channel", description="Select a channel")
    async def on_join_command(self, ctx: ApplicationContext,
                              channel: discord.VoiceChannel):
        await ctx.respond("Joining voice!")
        await channel.connect()
        voice: VoiceClient | None = ctx.voice_client

        if not voice:
            raise Exception("No voice client after connecting")

        # voice.play()

    @slash_command(name="leave", guild_ids=['272461623241736193'])
    async def on_leave_command(self, ctx: ApplicationContext):
        if ctx.voice_client is not None:
            await ctx.respond("Leaving voice")
            await ctx.voice_client.disconnect(force=False)
        else:
            await ctx.respond("Not connected to voice")


def setup_commands(bot: discord.Bot):
    bot.add_cog(VoiceBridgeCog())
