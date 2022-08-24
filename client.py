import asyncio
import os
import uuid
from typing import Callable, Optional

import discord
from twisted.internet import asyncioreactor
# Create event loop
from twisted.internet.defer import Deferred

from audio import AudioProcessThread

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Install asyncio reactor to play nice with pycord
asyncioreactor.install(loop)

from twisted.internet import reactor
from quarry.net import auth
from quarry.net.client import ClientFactory, SpawningClientProtocol
from twisted.internet.interfaces import IAddress, IListeningPort
from twisted.internet.protocol import DatagramProtocol

from bot import setup_commands
from packets.minecraft import EncodablePacket, RegisterPacket, BrandPacket, RequestSecretPacket, \
    UpdateStatePacket, \
    SecretPacket, CreateGroupPacket
from packets.voice import KeepAlivePacket, EncodableVoicePacket, PingPacket, AuthenticatePacket, \
    AuthenticateAckPacket, \
    MicPacket, GroupSoundPacket
from packets.voice.message import decode_voice_packet, encode_client_sent_voice_packet
from util import Buffer

compat_version = 14

used_plugin_channels = {'voicechat:player_state', 'voicechat:secret', 'voicechat:leave_group',
                        'voicechat:create_group', 'voicechat:request_secret', 'voicechat:set_group',
                        'voicechat:joined_group', 'voicechat:update_state',
                        'voicechat:player_states'}

class VoiceConnection(DatagramProtocol):
    host: str
    port: int

    player: uuid.UUID
    secret: uuid.UUID

    on_connected: Callable
    on_voice_data: Callable[[bytes], None]

    mic_sequence: int

    def __init__(self, host: str, port: int, player_id: uuid.UUID, secret: uuid.UUID,
                 on_connected: Callable,
                 on_voice_data: Callable[[bytes], None]):
        self.host = host
        self.port = port
        self.player = player_id
        self.secret = secret
        self.on_connected = on_connected
        self.on_voice_data = on_voice_data

        self.mic_sequence = 0

    def startProtocol(self):
        reactor.resolve(self.host).addCallback(self._on_host_resolved)

    def send_voice(self, data: bytes):
        """
        Sends opus-encoded audio data over the voice connection
        :param data: opus-encoded audio data
        :return:
        """
        pkt = MicPacket(data, False, self.mic_sequence)
        self.mic_sequence += 1

        self._send_packet(pkt)

    def datagramReceived(self, datagram: bytes, addr: tuple):
        buf = Buffer(datagram)

        # Decode & decrypt packet
        payload = decode_voice_packet(buf, self.secret)

        # Get type of packet
        packet_type = int.from_bytes(payload.unpack("c"), "big")

        if packet_type == AuthenticateAckPacket.ID:
            # Give connected callback
            self.on_connected()
        if packet_type == GroupSoundPacket.ID:
            pkt = GroupSoundPacket.from_buf(payload)
            self.on_voice_data(pkt.data)
        if packet_type == KeepAlivePacket.ID:
            # Respond with keepalive
            self._send_packet(KeepAlivePacket())
        elif packet_type == PingPacket.ID:
            # Respond with pong
            pkt = PingPacket.from_buf(payload)
            self._send_packet(PingPacket(pkt.id, pkt.timestamp))

    def _on_host_resolved(self, ip: str):
        self.transport.connect(ip, self.port)

        # Authenticate
        self._send_packet(AuthenticatePacket(self.player, self.secret))

    def _send_packet(self, packet: EncodableVoicePacket):
        buf = encode_client_sent_voice_packet(packet.ID, self.player, packet.to_buf(), self.secret)
        self.transport.write(buf)

class MinecraftClient(SpawningClientProtocol):
    server_host: str
    voice: Optional[VoiceConnection]
    voice_listener: Optional[IListeningPort]

    def __init__(self, factory: 'MinecraftClientFactory', addr: IAddress, host: str):
        super().__init__(factory, addr)
        self.server_host = host
        self.voice = None
        self.voice_listener = None

    def send_voice_data(self, data: bytes):
        if self.voice is not None:
            self.voice.send_voice(data)

    def connection_made(self):
        super().connection_made()
        factory: MinecraftClientFactory = self.factory
        factory.client = self

    def player_joined(self):
        super().player_joined()
        print("Joined the game")

    def packet_update_health(self, buf: Buffer):
        health = buf.unpack("f")

        # Discard rest of packet
        buf.discard()

        # Respawn if dead
        if health == 0:
            self._respawn()

    def packet_plugin_message(self, buf: Buffer):
        channel = buf.unpack_string()
        if channel == RegisterPacket.CHANNEL:
            pkt = RegisterPacket.from_buf(buf)
            if not used_plugin_channels.issubset(pkt.channels):
                self.close("unsupported server")
                reactor.stop()
        elif channel == BrandPacket.CHANNEL:
            self._vc_request_secret()
        elif channel == SecretPacket.CHANNEL:
            pkt = SecretPacket.from_buf(buf)
            self._create_new_voice_connection(pkt.port, pkt.player, pkt.secret)

        # Discard buffer contents if packet was not consumed already
        buf.discard()

    def on_voice_connected(self):
        self._vc_set_connected(True)
        self._vc_create_group("Discord Bridge")

    def on_voice_data(self, data: bytes):
        factory: MinecraftClientFactory = self.factory
        factory.on_mc_voice_data(data)

    def _reconnect_voice(self, port: int, player: uuid.UUID, secret: uuid.UUID):
        # Disconnect old listener if there was one
        if self.voice_listener is not None:
            self.voice_listener.stopListening().addCallback(
                lambda: self._create_new_voice_connection(port, player, secret))
        else:
            # Directly create new one if not
            self._create_new_voice_connection(port, player, secret)

    def _create_new_voice_connection(self, port: int, player: uuid.UUID, secret: uuid.UUID):
        # Create new voice connection & start listening
        self.voice = VoiceConnection(self.server_host, port, player, secret,
                                     self.on_voice_connected,
                                     self.on_voice_data)
        self.voice_listener = reactor.listenUDP(0, self.voice)

    def _vc_create_group(self, name: str):
        cg = CreateGroupPacket(name, None)
        self._send_pm_message(cg)

    def _vc_request_secret(self):
        rs = RequestSecretPacket(compat_version)
        self._send_pm_message(rs)

    def _vc_set_connected(self, connected):
        usp = UpdateStatePacket(disconnected=not connected, disabled=False)
        self._send_pm_message(usp)

    def _respawn(self):
        self.send_packet("client_status", Buffer.pack_varint(0))

    def _send_pm_message(self, packet: EncodablePacket):
        self.send_packet("plugin_message", Buffer.pack_string(packet.CHANNEL), packet.to_buf())

class MinecraftClientFactory(ClientFactory):
    protocol = MinecraftClient
    server_host: str

    on_mc_voice_data: Optional[Callable[[bytes], None]]

    client: Optional[MinecraftClient]

    def __init__(self, host):
        super().__init__(auth.OfflineProfile("Raqbot"))
        self.client = None
        self.server_host = host

    def buildProtocol(self, addr):
        return self.protocol(self, addr, self.server_host)

    def send_voice_data(self, data):
        if self.client is not None:
            self.client.send_voice_data(data)


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

    def on_processed_audio(data: bytes):
        reactor.callFromThread(minecraft.send_voice_data, data)

    mc_recv_voice_proc = AudioProcessThread(
        on_processed_audio,
        SAMPLE_RATE,
        FRAME_LENGTH,
        DISCORD_CHANNELS,
        MINECRAFT_CHANNELS
    )

    mc_recv_voice_proc.start()

    def on_discord_voice_data(data: bytes):
        # # Workaround bug where pycord seems to be buffering
        # # frames of emptiness and forwarding those to us next time someone
        # # speaks.
        # if len(data) > 3840:
        #     return

        mc_recv_voice_proc.enqueue(data)

    setup_commands(discord_bot, on_discord_voice_data)

    def on_mc_voice_data(data: bytes):
        ...
        # TODO: start thread & stuff
        # if len(discord_bot.voice_clients) > 0:
        #     discord_voice_client: VoiceClient = discord_bot.voice_clients[0]
        #     from discord import opus
        #     discord_voice_client.encoder = opus.Encoder()
        #     discord_voice_client.send_audio_packet(data, encode=True)

    minecraft.on_mc_voice_data = on_mc_voice_data

    # Start discord bot
    loop.create_task(discord_bot.start(bot_token))

    async def on_shutdown():
        await discord_bot.close()

    def on_shutdown_deferred():
        try:
            return Deferred.fromCoroutine(on_shutdown())
        # Somehow this is triggering an issue in either aiohttp or twisted
        # builtins.RuntimeError: await wasn't used with future
        except RuntimeError:
            pass

    reactor.addSystemEventTrigger('before', 'shutdown', lambda: on_shutdown_deferred)

    reactor.run()
    mc_recv_voice_proc.stop()

if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
