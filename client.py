import uuid
from typing import Callable, Optional

from quarry.net import auth
from quarry.net.client import ClientFactory, SpawningClientProtocol
from twisted.internet import reactor
from twisted.internet.interfaces import IAddress, IListeningPort
from twisted.internet.protocol import DatagramProtocol

from packets.minecraft import EncodablePacket, RegisterPacket, BrandPacket, RequestSecretPacket, UpdateStatePacket, \
    SecretPacket, CreateGroupPacket
from packets.voice import KeepAlivePacket, EncodableVoicePacket, PingPacket, AuthenticatePacket, AuthenticateAckPacket
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

    on_connected: Callable

    def __init__(self, host: str, port: int, player_id: uuid.UUID, secret: uuid.UUID, on_connected: Callable):
        self.host = host
        self.port = port
        self.player = player_id
        self.secret = secret
        self.on_connected = on_connected

    def startProtocol(self):
        reactor.resolve(self.host).addCallback(self.on_host_resolved)

    def on_host_resolved(self, ip: str):
        self.transport.connect(ip, self.port)

        # Authenticate
        self._send_packet(AuthenticatePacket(self.player, self.secret))

    def datagramReceived(self, datagram: bytes, addr: tuple):
        buf = Buffer(datagram)

        # Decode & decrypt packet
        payload = decode_voice_packet(buf, self.secret)

        # Get type of packet
        packet_type = int.from_bytes(payload.unpack("c"), "big")

        if packet_type == AuthenticateAckPacket.ID:
            # Give connected callback
            self.on_connected()
        if packet_type == KeepAlivePacket.ID:
            # Respond with keepalive
            self._send_packet(KeepAlivePacket())
        elif packet_type == PingPacket.ID:
            # Respond with pong
            pkt = PingPacket.from_buf(payload)
            self._send_packet(PingPacket(pkt.id, pkt.timestamp))

    def _send_packet(self, packet: EncodableVoicePacket):
        buf = encode_client_sent_voice_packet(packet.ID, self.player, packet.to_buf(), self.secret)
        self.transport.write(buf)


class VoiceChatClientProtocol(SpawningClientProtocol):
    server_host: str
    voice: Optional[VoiceConnection]
    voice_listener: Optional[IListeningPort]

    def __init__(self, factory: 'VoiceChatClientFactory', addr: IAddress, host: str):
        super().__init__(factory, addr)
        self.server_host = host
        self.voice = None
        self.voice_listener = None

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
        self.voice = VoiceConnection(self.server_host, port, player, secret, self.on_voice_connected)
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


class VoiceChatClientFactory(ClientFactory):
    protocol = VoiceChatClientProtocol

    server_host: str

    def __init__(self, host):
        super().__init__(auth.OfflineProfile("Raqbot"))
        self.server_host = host

    def buildProtocol(self, addr):
        return self.protocol(self, addr, self.server_host)


def main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("-p", "--port", default=25565, type=int)
    args = parser.parse_args(argv)

    factory = VoiceChatClientFactory(args.host)

    factory.connect(args.host, args.port)

    reactor.run()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
