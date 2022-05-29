import asyncio
import os
import uuid
from typing import Callable, Optional

import discord
from discord import VoiceClient
from opuslib import APPLICATION_VOIP
from twisted.internet import asyncioreactor

# Create event loop
from audio import VoiceChatAudioDecoder, VoiceChatAudioEncoder

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
from packets.minecraft import EncodablePacket, RegisterPacket, BrandPacket, RequestSecretPacket, UpdateStatePacket, \
    SecretPacket, CreateGroupPacket
from packets.voice import KeepAlivePacket, EncodableVoicePacket, PingPacket, AuthenticatePacket, AuthenticateAckPacket, \
    PlayerSoundPacket, MicPacket, GroupSoundPacket
from packets.voice.message import decode_voice_packet, encode_client_sent_voice_packet
from util import Buffer

compat_version = 14

used_plugin_channels = {'voicechat:player_state', 'voicechat:secret', 'voicechat:leave_group',
                        'voicechat:create_group', 'voicechat:request_secret', 'voicechat:set_group',
                        'voicechat:joined_group', 'voicechat:update_state', 'voicechat:player_states'}


class VoiceConnection(DatagramProtocol):
    host: str
    port: int

    player: uuid.UUID
    secret: uuid.UUID

    decoder: VoiceChatAudioDecoder

    on_connected: Callable
    on_voice_data: Callable[[bytes], None]

    mic_sequence: int

    def __init__(self, host: str, port: int, player_id: uuid.UUID, secret: uuid.UUID, on_connected: Callable,
                 on_voice_data: Callable[[bytes], None]):
        self.host = host
        self.port = port
        self.player = player_id
        self.secret = secret
        self.on_connected = on_connected
        self.on_voice_data = on_voice_data

        self.decoder = VoiceChatAudioDecoder()
        self.encoder = VoiceChatAudioEncoder(application=APPLICATION_VOIP)

        self.mic_sequence = 0

    def startProtocol(self):
        reactor.resolve(self.host).addCallback(self._on_host_resolved)

    def send_voice(self, data: bytes):
        """
        Sends PCM-encoded
        :param data:
        :return:
        """
        encoded_data = self.encoder.encode(data)
        pkt = MicPacket(encoded_data, False, self.mic_sequence)
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
            # TODO: use sequence info to re-order packets before sending them through to discord
            # TODO: for now, simply send them all to discord in whatever order they were received
            pcm_data = self.decoder.decode(pkt.data)
            self.on_voice_data(pcm_data)
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
        self.voice = VoiceConnection(self.server_host, port, player, secret, self.on_voice_connected,
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

    setup_commands(discord_bot, minecraft.send_voice_data)

    def on_mc_voice_data(data: bytes):
        if len(discord_bot.voice_clients) > 0:
            discord_voice_client: VoiceClient = discord_bot.voice_clients[0]
            from discord import opus
            discord_voice_client.encoder = opus.Encoder()
            discord_voice_client.send_audio_packet(data, encode=True)

    minecraft.on_mc_voice_data = on_mc_voice_data

    # Start discord bot
    loop.create_task(discord_bot.start(bot_token))

    reactor.run()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
