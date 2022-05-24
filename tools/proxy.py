from quarry.net.proxy import DownstreamFactory, Bridge
from twisted.internet import reactor

from packets.minecraft import RegisterPacket, BrandPacket, RequestSecretPacket, SecretPacket, PlayerStatePacket, \
    PlayerStatesPacket, UpdateStatePacket, JoinedGroupPacket, CreateGroupPacket, JoinGroupPacket, LeaveGroupPacket
from util import Buffer


# Upstream = server, downstream = client
class MinecraftProxyBridge(Bridge):
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

        buf.restore()
        self.downstream.send_packet("plugin_message", buf.read())

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

    @staticmethod
    def _handle_downstream(channel: str, buf: Buffer):
        if channel == RegisterPacket.CHANNEL:
            print(RegisterPacket.from_buf(buf))
        elif channel == BrandPacket.CHANNEL:
            print(BrandPacket.from_buf(buf))
        elif channel == SecretPacket.CHANNEL:
            print(SecretPacket.from_buf(buf))
        elif channel == PlayerStatesPacket.CHANNEL:
            print(PlayerStatesPacket.from_buf(buf))
        elif channel == PlayerStatePacket.CHANNEL:
            print(PlayerStatePacket.from_buf(buf))
        elif channel == JoinedGroupPacket.CHANNEL:
            print(JoinedGroupPacket.from_buf(buf))


class MinecraftDownstreamFactory(DownstreamFactory):
    bridge_class = MinecraftProxyBridge
    motd = "Proxy Server"
    online_mode = False


def main(argv):
    # Parse options
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--listen-host", default="", help="address to listen on")
    parser.add_argument("-p", "--listen-port", default=25565, type=int, help="port to listen on")
    parser.add_argument("-b", "--connect-host", default="127.0.0.1", help="address to connect to")
    parser.add_argument("-q", "--connect-port", default=25565, type=int, help="port to connect to")
    args = parser.parse_args(argv)

    # Create factory
    factory = MinecraftDownstreamFactory()
    factory.connect_host = args.connect_host
    factory.connect_port = args.connect_port

    # Listen
    factory.listen(args.listen_host, args.listen_port)
    reactor.run()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
