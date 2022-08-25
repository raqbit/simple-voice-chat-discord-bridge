import asyncio
import logging
import os

import discord
from discord import VoiceClient
from twisted.internet import asyncioreactor

from audio.process import AudioProcessThread

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Install asyncio reactor to play nice with pycord
# NOTE: THIS NEEDS TO BE BEFORE THE mc_bot IMPORT
asyncioreactor.install(loop)

from mc_bot import MinecraftClientFactory

from twisted.internet import reactor

from discord_bot import setup_commands

logging.basicConfig()

SAMPLE_RATE = 48000  # 48kHz
FRAME_LENGTH = 20  # 20 ms
DISCORD_CHANNELS = 2
MINECRAFT_CHANNELS = 1


def main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("-p", "--port", default=25565, type=int)
    args = parser.parse_args(argv)

    bot_token = os.getenv("BOT_TOKEN")

    if bot_token is None:
        raise Exception("no discord bot token provided")

    discord_bot = discord.Bot()
    minecraft = MinecraftClientFactory(args.host)
    minecraft.connect(args.host, args.port)

    def on_processed_discord_audio(data: bytes):
        reactor.callFromThread(minecraft.send_voice_data, data)

    def on_processed_minecraft_audio(data: bytes):
        if len(discord_bot.voice_clients) >= 1:
            discord_voice_client = discord_bot.voice_clients[0]
            if isinstance(discord_voice_client, VoiceClient) and discord_voice_client.is_connected():
                discord_voice_client.send_audio_packet(data, encode=False)

    mc_recv_voice_proc = AudioProcessThread(
        on_processed_discord_audio,
        SAMPLE_RATE,
        FRAME_LENGTH,
        DISCORD_CHANNELS,
        MINECRAFT_CHANNELS
    )

    mc_recv_voice_proc.start()

    discord_recv_voice_proc = AudioProcessThread(
        on_processed_minecraft_audio,
        SAMPLE_RATE,
        FRAME_LENGTH,
        MINECRAFT_CHANNELS,
        DISCORD_CHANNELS,
        decode=True,
    )

    discord_recv_voice_proc.start()

    def on_discord_voice_data(data: bytes):
        # # Workaround bug where pycord seems to be buffering
        # # frames of emptiness and forwarding those to us next time someone
        # # speaks.
        # if len(data) > 3840:
        #     return

        mc_recv_voice_proc.enqueue(data)

    setup_commands(discord_bot, on_discord_voice_data)

    def on_mc_voice_data(data: bytes):
        discord_recv_voice_proc.enqueue(data)

    minecraft.on_mc_voice_data = on_mc_voice_data

    # Start discord bot
    loop.create_task(discord_bot.start(bot_token))

    # Run Minecraft client until SIGTERM
    reactor.run()

    print('Shutting down audio process threads')

    # Shutdown audio process threads
    discord_recv_voice_proc.stop()
    mc_recv_voice_proc.stop()

    print('Stopping discord bot')

    # Stop discord bot
    loop.run_until_complete(discord_bot.close())


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
