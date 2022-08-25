import uuid

from cryptography.hazmat.primitives.ciphers import Cipher
from quarry.net.proxy import DownstreamFactory, Bridge
from transmitm import Tap, UDPProxy
from twisted.internet import reactor

from bridge.audio import OpusDecoder
from bridge.packets.minecraft import RegisterPacket, BrandPacket, RequestSecretPacket, SecretPacket, PlayerStatePacket, \
    PlayerStatesPacket, UpdateStatePacket, JoinedGroupPacket, CreateGroupPacket, JoinGroupPacket, LeaveGroupPacket, \
    EncodablePacket, PlayerState
from bridge.packets.voice import MicPacket, KeepAlivePacket, PingPacket, PlayerSoundPacket, GroupSoundPacket, \
    LocationSoundPacket, AuthenticatePacket, AuthenticateAckPacket
from bridge.packets.voice.message import decode_voice_packet, decode_client_sent_voice_packet
from bridge.util import Buffer


class VoiceInterceptor(Tap):
    interceptor_port: int
    downstream_port: int

    secrets: dict[uuid.UUID, uuid.UUID]

    cipher: Cipher

    decoder: OpusDecoder

    def __init__(self, interceptor_port: int):
        self.interceptor_port = interceptor_port
        self.secrets = {}
        self._peer_to_player = {}

        self.decoder = OpusDecoder(48000, int((48000/1000)*20), 1)

    def handle(self, data, ip_tuple):
        peer, proxy = ip_tuple

        buf = Buffer(data)

        is_downstream = peer[1] == self.downstream_port

        if is_downstream:
            # We're receiving a server-sent packet, so we need to figure out
            # which client we're receiving for so that we can figure out the
            # correct player uuid, which we can then use to obtain the right secret
            #
            # Sadly, this is not possible with the transmitm package, as the source-ports
            # it uses for communicating with upstream cannot be defined nor retrieved, so when we
            # receive packets we are unable to match them to the client.
            # So, as a hack, this assumes the first secret is the secret to use, which works for 1-client proxy
            # scenarios
            payload = decode_voice_packet(buf, list(self.secrets.values())[0])
        else:
            # We're receiving a client-sent packet, so we pass in all the secrets
            # and the function will read the sender-id to get the appropriate secret
            (sender, payload) = decode_client_sent_voice_packet(buf, self.secrets)

        arrow = ">>"

        if is_downstream:
            arrow = "<<"
        prefix = f"🎙️ {arrow}"

        packet_type = int.from_bytes(payload.unpack("c"), "big")

        if packet_type == MicPacket.ID:
            pkt = MicPacket.from_buf(payload)
            print(f"{prefix} Mic len={len(pkt.data)} sequence={pkt.sequence} whispering={pkt.whispering}")
            print(f"Decoded len: {len(self.decoder.decode(pkt.data))}")
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
            print(f"{prefix} AuthenticateAck")
        if packet_type == PingPacket.ID:
            pkt = PingPacket.from_buf(payload)
            print(f"{prefix} Ping id={pkt.id} timestamp={pkt.timestamp}")
        if packet_type == KeepAlivePacket.ID:
            print(f"{prefix} KeepAlive")

        return data


# Upstream = server, downstream = client
class MinecraftProxyBridge(Bridge):
    _voice_interceptor: VoiceInterceptor

    _prefix = "⛏️"

    def __init__(self, downstream_factory, downstream):
        super().__init__(downstream_factory, downstream)

        self._voice_interceptor = downstream_factory.voice_interceptor

    def packet_upstream_plugin_message(self, buf: Buffer):
        buf.save()
        channel = buf.unpack_string()

        self._handle_upstream(channel, buf, f"{self._prefix} >>")

        buf.restore()
        self.upstream.send_packet("plugin_message", buf.read())

    def packet_downstream_plugin_message(self, buf: Buffer):
        buf.save()
        channel = buf.unpack_string()

        self._handle_downstream(channel, buf, f"{self._prefix} <<")

    @staticmethod
    def _handle_upstream(channel: str, buf: Buffer, prefix: str):
        if channel == RegisterPacket.CHANNEL:
            pkt = RegisterPacket.from_buf(buf)
            print(f"{prefix} Register channels=[{', '.join(pkt.channels)}]")
        elif channel == BrandPacket.CHANNEL:
            pkt = BrandPacket.from_buf(buf)
            print(f"{prefix} Brand brand={pkt.brand}")
        elif channel == UpdateStatePacket.CHANNEL:
            pkt = UpdateStatePacket.from_buf(buf)
            print(f"{prefix} UpdateState disabled={pkt.disabled} disconnected={pkt.disconnected}")
        elif channel == RequestSecretPacket.CHANNEL:
            pkt = RequestSecretPacket.from_buf(buf)
            print(f"{prefix} RequestSecret compat_version={pkt.compat_version}")
        elif channel == CreateGroupPacket.CHANNEL:
            pkt = CreateGroupPacket.from_buf(buf)
            print(f"{prefix} CreateGroup name={pkt.name} password={pkt.password}")
        elif channel == JoinGroupPacket.CHANNEL:
            pkt = JoinGroupPacket.from_buf(buf)
            print(f"{prefix} JoinGroup group={pkt.group} password={pkt.password}")
        elif channel == LeaveGroupPacket.CHANNEL:
            print(f"{prefix} LeaveGroup")
            pass

    def _handle_downstream(self, channel: str, buf: Buffer, prefix: str):
        if channel == RegisterPacket.CHANNEL:
            pkt = RegisterPacket.from_buf(buf)
            print(f"{prefix} Register channels=[{', '.join(pkt.channels)}]")
        elif channel == BrandPacket.CHANNEL:
            pkt = BrandPacket.from_buf(buf)
            print(f"{prefix} Brand brand={pkt.brand}")
        elif channel == SecretPacket.CHANNEL:
            pkt = SecretPacket.from_buf(buf)
            print(
                (
                    f"{prefix} Secret "
                    f"secret={pkt.secret} "
                    f"port={pkt.port} "
                    f"codec={pkt.codec} "
                    f"mtu={pkt.mtu} "
                    f"dist={pkt.dist} "
                    f"fade_dist={pkt.fade_dist} "
                    f"crouch_dist={pkt.crouch_dist} "
                    f"whisper_dist={pkt.whisper_dist} "
                    f"keep_alive={pkt.keep_alive} "
                    f"groups_enabled={pkt.groups_enabled}"
                ))
            self._intercept_voice(pkt)
            return
        elif channel == PlayerStatesPacket.CHANNEL:
            pkt = PlayerStatesPacket.from_buf(buf)
            states = ' '.join([f"{player}=({self._format_player_state(state)})"
                               for player, state in pkt.states.items()])
            print(
                f"{prefix} PlayerStates {states}")
        elif channel == PlayerStatePacket.CHANNEL:
            pkt = PlayerStatePacket.from_buf(buf)
            print(f"{prefix} PlayerState {self._format_player_state(pkt.state)}")
        elif channel == JoinedGroupPacket.CHANNEL:
            pkt = JoinedGroupPacket.from_buf(buf)
            print(f"{prefix} JoinedGroup group={pkt.group} wrong_password={pkt.wrong_password}")

        # Passthrough un-handled messages
        buf.restore()
        self.downstream.send_packet("plugin_message", buf.read())

    @staticmethod
    def _format_player_state(state: PlayerState) -> str:
        return f'name={state.name} disabled={state.disabled} disconnected={state.disconnected}'

    def _intercept_voice(self, pkt: SecretPacket):
        # Setup proxy with connection secret & port of udp voice listener
        self._voice_interceptor.secrets[pkt.player] = pkt.secret
        self._voice_interceptor.downstream_port = pkt.port
        self._voice_interceptor.mtu = pkt.mtu
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
