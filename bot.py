from typing import Callable

import discord.client
from discord import slash_command, ApplicationContext, option, VoiceClient, sinks


class VoiceBridgeAudioSink(sinks.Sink):
    _on_voice_received: Callable[[bytes], None]

    def __init__(self, on_voice_received: Callable[[bytes], None]):
        super().__init__(filters=None)
        self._on_voice_received = on_voice_received

    def write(self, data, user):
        self._on_voice_received(data)


class VoiceBridgeCog(discord.Cog):
    sink: VoiceBridgeAudioSink

    def __init__(self, on_voice_received: Callable):
        self.sink = VoiceBridgeAudioSink(on_voice_received)
        pass

    @slash_command(name="join", description="Makes the bot join the given voice chat", guild_ids=['272461623241736193'])
    @option("channel", description="Select a channel")
    async def on_join_command(self, ctx: ApplicationContext,
                              channel: discord.VoiceChannel):
        await ctx.respond("Joining voice!")
        await channel.connect()
        voice: VoiceClient | None = ctx.voice_client

        if not voice:
            raise Exception("No voice client after connecting")

        voice.start_recording(self.sink, self._on_voice_recording_stop)

    async def _on_voice_recording_stop(self, _: VoiceBridgeAudioSink):
        print("Stopped recording")

    @slash_command(name="leave", guild_ids=['272461623241736193'])
    async def on_leave_command(self, ctx: ApplicationContext):
        if ctx.voice_client is not None:
            await ctx.respond("Leaving voice")
            await ctx.voice_client.disconnect(force=False)
        else:
            await ctx.respond("Not connected to voice")


def setup_commands(bot: discord.Bot, on_voice_received: Callable[[bytes], None]):
    bot.add_cog(VoiceBridgeCog(on_voice_received))
