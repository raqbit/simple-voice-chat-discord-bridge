import uuid

from cryptography.hazmat.primitives.ciphers import Cipher
from quarry.net.proxy import DownstreamFactory, Bridge
from transmitm import Tap, UDPProxy
from twisted.internet import reactor

from packets.minecraft import RegisterPacket, BrandPacket, RequestSecretPacket, SecretPacket, PlayerStatePacket, \
    PlayerStatesPacket, UpdateStatePacket, JoinedGroupPacket, CreateGroupPacket, JoinGroupPacket, LeaveGroupPacket, \
    EncodablePacket
from packets.voice import MicPacket, KeepAlivePacket, PingPacket, PlayerSoundPacket, GroupSoundPacket, \
    LocationSoundPacket, AuthenticatePacket, AuthenticateAckPacket
from packets.voice.message import NetworkMessage
from util import Buffer


class VoiceInterceptor(Tap):
    interceptor_port: int
    downstream_port: int

    # FIXME: secret is unique per connection, so this will corrupt older connections when a new one comes in
    # FIXME: make this a dictionary from player uuid to secret
    secret: uuid.UUID

    cipher: Cipher

    def __init__(self, interceptor_port: int):
        self.interceptor_port = interceptor_port

    def handle(self, data, ip_tuple):
        peer, proxy = ip_tuple

        full_buf = Buffer(data)

        is_downstream = peer[1] == self.downstream_port

        if is_downstream:
            payload = NetworkMessage.from_buf(full_buf, self.secret)
        else:
            payload = NetworkMessage.from_client_buf(full_buf, self.secret)

        arrow = ">>"

        if is_downstream:
            arrow = "<<"
        prefix = f"🎙️ {arrow}"

        packet_type = int.from_bytes(payload.unpack("c"), "big")

        if packet_type == MicPacket.ID:
            pkt = MicPacket.from_buf(payload)
            print(f"{prefix} Mic len={len(pkt.data)} sequence={pkt.sequence} whispering={pkt.whispering}")
        if packet_type == PlayerSoundPacket.ID:
            pkt = PlayerSoundPacket.from_buf(payload)
            print(
                f"{prefix} PlayerSound sender={pkt.sender} len={len(pkt.data)} sequence={pkt.sequence} whispering={pkt.whispering}")
        if packet_type == GroupSoundPacket.ID:
            pkt = GroupSoundPacket.from_buf(payload)
            print(f"{prefix} GroupSound sender={pkt.sender} len={len(pkt.data)} sequence={pkt.sequence}")
        if packet_type == LocationSoundPacket.ID:
            pkt = LocationSoundPacket.from_buf(payload)
            print(
                f"{prefix} LocationSound sender={pkt.sender} len={len(pkt.data)} sequence={pkt.sequence} location={pkt.location}")
        if packet_type == AuthenticatePacket.ID:
            pkt = AuthenticatePacket.from_buf(payload)
            print(f"{prefix} Authenticate player={pkt.player_uuid} secret={pkt.secret}")
        if packet_type == AuthenticateAckPacket.ID:
            pkt = AuthenticateAckPacket.from_buf(payload)
            print(f"{prefix} AuthenticateAck")
        if packet_type == PingPacket.ID:
            print(f"{prefix} Ping")
        if packet_type == KeepAlivePacket.ID:
            print(f"{prefix} KeepAlive")

        return data


# Upstream = server, downstream = client
class MinecraftProxyBridge(Bridge):
    _voice_interceptor: VoiceInterceptor

    def __init__(self, downstream_factory, downstream):
        super().__init__(downstream_factory, downstream)

        self._voice_interceptor = downstream_factory.voice_interceptor

    def packet_upstream_plugin_message(self, buf: Buffer):
        buf.save()
        channel = buf.unpack_string()
        print(f" >> plugin:{channel}")

        self._handle_upstream(channel, buf)

        buf.restore()
        self.upstream.send_packet("plugin_message", buf.read())

    def packet_downstream_plugin_message(self, buf: Buffer):
        buf.save()
        channel = buf.unpack_string()
        print(f" << plugin:{channel}")

        self._handle_downstream(channel, buf)

    @staticmethod
    def _handle_upstream(channel: str, buf: Buffer):
        if channel == RegisterPacket.CHANNEL:
            print(RegisterPacket.from_buf(buf))
        elif channel == BrandPacket.CHANNEL:
            print(BrandPacket.from_buf(buf))
        elif channel == UpdateStatePacket.CHANNEL:
            print(UpdateStatePacket.from_buf(buf))
        elif channel == RequestSecretPacket.CHANNEL:
            print(RequestSecretPacket.from_buf(buf))
        elif channel == CreateGroupPacket.CHANNEL:
            print(CreateGroupPacket.from_buf(buf))
        elif channel == JoinGroupPacket.CHANNEL:
            print(JoinGroupPacket.from_buf(buf))
        elif channel == LeaveGroupPacket.CHANNEL:
            pass

    def _handle_downstream(self, channel: str, buf: Buffer):
        if channel == RegisterPacket.CHANNEL:
            print(RegisterPacket.from_buf(buf))
        elif channel == BrandPacket.CHANNEL:
            print(BrandPacket.from_buf(buf))
        elif channel == SecretPacket.CHANNEL:
            self._intercept_voice(buf)
            return
        elif channel == PlayerStatesPacket.CHANNEL:
            print(PlayerStatesPacket.from_buf(buf))
        elif channel == PlayerStatePacket.CHANNEL:
            print(PlayerStatePacket.from_buf(buf))
        elif channel == JoinedGroupPacket.CHANNEL:
            print(JoinedGroupPacket.from_buf(buf))

        # Passthrough un-handled messages
        buf.restore()
        self.downstream.send_packet("plugin_message", buf.read())

    def _intercept_voice(self, buf: Buffer):
        pkt = SecretPacket.from_buf(buf)
        print(pkt)

        # Setup proxy with connection secret & port of udp voice listener
        self._voice_interceptor.secret = pkt.secret
        self._voice_interceptor.downstream_port = pkt.port
        pkt.port = self._voice_interceptor.interceptor_port
        self._send_plugin_message(pkt)

    def _send_plugin_message(self, packet: EncodablePacket):
        self.downstream.send_packet("plugin_message", Buffer.pack_string(packet.CHANNEL), packet.to_buf())


class MinecraftDownstreamFactory(DownstreamFactory):
    bridge_class = MinecraftProxyBridge
    motd = "Proxy Server"
    online_mode = False

    voice_interceptor: VoiceInterceptor


def main(argv):
    # Parse options
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--listen-host", default="", help="address to listen on")
    parser.add_argument("-p", "--listen-port", default=25566, type=int, help="port to listen on")
    parser.add_argument("-v", "--listen-voice-port", default=25567, type=int, help="voice port to listen on")
    parser.add_argument("-b", "--connect-host", default="127.0.0.1", help="address to connect to")
    parser.add_argument("-q", "--connect-port", default=25565, type=int, help="port to connect to")
    args = parser.parse_args(argv)

    # Create UDP proxy for intercepting voice packets
    voice_intercept = VoiceInterceptor(args.listen_voice_port)
    voice_proxy = UDPProxy(args.connect_host, 24454, voice_intercept.interceptor_port)
    voice_proxy.add_tap(voice_intercept)

    # Create factory
    minecraft_factory = MinecraftDownstreamFactory()
    minecraft_factory.connect_host = args.connect_host
    minecraft_factory.connect_port = args.connect_port

    minecraft_factory.voice_interceptor = voice_intercept

    # Listen
    minecraft_factory.listen(args.listen_host, args.listen_port)
    voice_proxy.spawn()
    reactor.run()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
