import uuid

from quarry.net import auth
from quarry.net.client import ClientFactory, SpawningClientProtocol
from twisted.internet import reactor

from packets.encodable import EncodablePacket
from packets.minecraft.minecraft import RegisterPacket, BrandPacket
from packets.minecraft.voicechat import RequestSecretPacket, UpdateStatePacket, SecretPacket, CreateGroupPacket
from util import Buffer

compat_version = 14

used_plugin_channels = {'voicechat:player_state', 'voicechat:secret', 'voicechat:leave_group',
                        'voicechat:create_group', 'voicechat:request_secret', 'voicechat:set_group',
                        'voicechat:joined_group', 'voicechat:update_state', 'voicechat:player_states'}


class VoiceChatClientProtocol(SpawningClientProtocol):
    secret: uuid.UUID
    port: int

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
            self.secret = pkt.secret
            self.port = pkt.port
            print(f"Received voice chat secret: {self.secret}")
            self._vc_set_connected(True)
            self._vc_create_group("Discord Bridge")

        # Discard buffer contents if packet was not consumed already
        buf.discard()

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

    def __init__(self):
        super().__init__(auth.OfflineProfile("Raqbot"))


def main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("-p", "--port", default=25565, type=int)
    args = parser.parse_args(argv)

    factory = VoiceChatClientFactory()

    factory.connect(args.host, args.port)

    reactor.run()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
