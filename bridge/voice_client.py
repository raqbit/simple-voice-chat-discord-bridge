import uuid
from typing import Callable

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from .packets.voice import MicPacket, AuthenticateAckPacket, GroupSoundPacket, KeepAlivePacket, PingPacket, \
    AuthenticatePacket, EncodableVoicePacket
from .packets.voice.message import decode_voice_packet, encode_client_sent_voice_packet
from .util import Buffer


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
