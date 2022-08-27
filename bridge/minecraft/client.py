import logging
import uuid
from typing import Optional, Callable

from quarry.net import auth
from quarry.net.client import SpawningClientProtocol, ClientFactory
from quarry.types.uuid import UUID
from twisted.internet import reactor
from twisted.internet.interfaces import IListeningPort, IAddress
from twisted.internet.tcp import Connector

from bridge import voice
from bridge.minecraft.packets import RegisterPacket, BrandPacket, SecretPacket, CreateGroupPacket, RequestSecretPacket, \
    UpdateStatePacket, EncodablePacket
from bridge.util.encodable import Buffer
from bridge.voice_client import VoiceConnection

used_plugin_channels = {'voicechat:player_state', 'voicechat:secret', 'voicechat:leave_group',
                        'voicechat:create_group', 'voicechat:request_secret', 'voicechat:set_group',
                        'voicechat:joined_group', 'voicechat:update_state',
                        'voicechat:player_states'}


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

    def packet_update_health(self, buf: Buffer):
        health = buf.unpack("f")

        # Discard rest of packet
        buf.discard()

        # Respawn if dead
        if health == 0:
            self.logger.info("Player died")
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
        self.logger.info("Connected to voice chat")
        self._vc_set_connected(True)
        self._vc_create_group("Discord Bridge")
        self.logger.info("Created voice chat group")

    def on_voice_data(self, data: bytes):
        factory: MinecraftClientFactory = self.factory
        factory.on_mc_voice_data(data)

    def _reconnect_voice(self, port: int, player: uuid.UUID, secret: uuid.UUID):
        # Disconnect old listener if there was one
        if self.voice_listener is not None:
            self.voice_listener.stopListening() \
                .addCallback(lambda: self._create_new_voice_connection(port, player, secret))
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
        rs = RequestSecretPacket(voice.compat_version)
        self._send_pm_message(rs)

    def _vc_set_connected(self, connected):
        usp = UpdateStatePacket(disconnected=not connected, disabled=False)
        self._send_pm_message(usp)

    def _respawn(self):
        self.send_packet("client_status", Buffer.pack_varint(0))
        self.logger.info("Respawned")

    def _send_pm_message(self, packet: EncodablePacket):
        self.send_packet("plugin_message", Buffer.pack_string(packet.CHANNEL), packet.to_buf())

class MinecraftClientFactory(ClientFactory):
    protocol = MinecraftClient
    server_host: str

    on_mc_voice_data: Optional[Callable[[bytes], None]]

    client: Optional[MinecraftClient]

    def __init__(self, host, _uuid: Optional[str], name: str, token: Optional[str], on_audio: Optional[Callable[[bytes], None]]):
        if _uuid is None or token is None:
            profile = auth.OfflineProfile("VoiceChatBridge")
        else:
            profile = auth.Profile(None, token, name, UUID.from_hex(hex=_uuid))

        super().__init__(profile)
        self.client = None
        self.server_host = host

        self.on_mc_voice_data = on_audio

        self.logger = logging.getLogger("%s{%s}" % (
            self.__class__.__name__,
            self.server_host))
        self.logger.setLevel(self.log_level)

    def startedConnecting(self, connector):
        self.logger.info("Started connecting")
        super().startedConnecting(connector)

    def clientConnectionFailed(self, connector: Connector, reason):
        super().clientConnectionFailed(connector, reason)
        self.logger.warning(f"Connection failed")
        # connector.connect()

    def clientConnectionLost(self, connector: Connector, reason):
        super().clientConnectionLost(connector, reason)
        self.logger.warning(f"Connection lost")
        # TODO: backoff / do not retry if banned or something
        # connector.connect()

    def buildProtocol(self, addr):
        return self.protocol(self, addr, self.server_host)

    def send_voice_data(self, data):
        if self.client is not None:
            self.client.send_voice_data(data)
