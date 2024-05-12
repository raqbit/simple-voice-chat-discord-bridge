import asyncio
import logging
import os

import discord
from discord import VoiceClient
from minecraft_launcher_lib.exceptions import InvalidRefreshToken
from twisted.internet import reactor

from bridge.minecraft.auth import refresh_auth as refresh_minecraft_auth
from bridge.minecraft.client import MinecraftClientFactory

from . import audio
from .audio.process import AudioProcessThread
from .discord_bot import setup_commands


class DiscordMinecraftBridge:

    def __init__(
            self,
            mc_host: str,
            mc_port: int,
            discord_bot_token: str,
            mc_uuid: str | None = None,
            mc_name: str | None = None,
            mc_token: str | None = None
    ):
        self.mc_host = mc_host
        self.mc_port = mc_port
        self.discord_bot_token = discord_bot_token

        self.loop = asyncio.get_event_loop_policy().get_event_loop()

        self.discord = discord.Bot()
        setup_commands(self.discord, self._on_discord_audio)

        self.minecraft = MinecraftClientFactory(mc_host, mc_uuid, mc_name, mc_token, self._on_minecraft_audio)

        self.discord_process = AudioProcessThread(
            self._on_processed_discord_audio,
            audio.SAMPLE_RATE,
            audio.FRAME_LENGTH,
            audio.DISCORD_CHANNELS,
            audio.MINECRAFT_CHANNELS
        )

        self.minecraft_process = AudioProcessThread(
            self._on_processed_minecraft_audio,
            audio.SAMPLE_RATE,
            audio.FRAME_LENGTH,
            audio.MINECRAFT_CHANNELS,
            audio.DISCORD_CHANNELS,
            decode=True
        )

        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.setLevel(logging.INFO)

    def run(self):
        # Setup connection to Minecraft & start discord
        self._connect()

        # Start audio processing threads
        self.minecraft_process.start()
        self.discord_process.start()

        # Run Twisted reactor until shutdown
        reactor.run()

        # Shutdown
        self._shutdown()

    def _on_discord_audio(self, raw_frame: bytes):
        # # Workaround bug where pycord seems to be buffering
        # # frames of emptiness and forwarding those to us next time someone
        # # speaks.
        # if len(data) > 3840:
        #     return
        self.discord_process.enqueue(raw_frame)

    def _on_minecraft_audio(self, encoded_frame: bytes):
        self.minecraft_process.enqueue(encoded_frame)

    def _on_processed_discord_audio(self, encoded_frame: bytes):
        reactor.callFromThread(self.minecraft.send_voice_data, encoded_frame)

    def _on_processed_minecraft_audio(self, encoded_frame: bytes):
        if len(self.discord.voice_clients) >= 1:
            discord_voice_client = self.discord.voice_clients[0]
            if isinstance(discord_voice_client, VoiceClient) and discord_voice_client.is_connected():
                discord_voice_client.send_audio_packet(encoded_frame, encode=False)

    def _connect(self):
        self.minecraft.connect(self.mc_host, self.mc_port)

        self.loop.create_task(self.discord.start(self.discord_bot_token))

    def _shutdown(self):
        self.logger.info('Shutting down audio process threads')

        # Shutdown audio process threads
        self.discord_process.stop()
        self.minecraft_process.stop()

        self.logger.info('Stopping discord bot')

        # Stop discord bot
        self.loop.run_until_complete(self.discord.close())


def main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("-p", "--port", default=25565, type=int)
    args = parser.parse_args(argv)

    logger = logging.getLogger("main")
    logger.setLevel(logging.INFO)

    logging.basicConfig()

    discord_token = os.getenv("BOT_TOKEN")

    if discord_token is None:
        raise Exception("no discord bot token provided")

    client_id = os.getenv("MSA_CLIENT_ID")

    kwargs = {}

    if client_id is not None:
        logger.info("Client ID set, attempting login into Minecraft account")
        try:
            mc_uuid, mc_name, mc_token = refresh_minecraft_auth(client_id)
        except InvalidRefreshToken:
            logger.error("Refresh token invalid, please login again")
            sys.exit(1)
        logger.info(f"Successfully logged in as {mc_name}")
        kwargs['mc_uuid'] = mc_uuid
        kwargs['mc_name'] = mc_name
        kwargs['mc_token'] = mc_token

    bridge = DiscordMinecraftBridge(args.host, args.port, discord_token, **kwargs)

    bridge.run()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
