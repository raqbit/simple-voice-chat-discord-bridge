import abc

from bridge.util.encodable import Decodable, Encodable


class ChannelPacket(abc.ABC):
    CHANNEL: str


class EncodablePacket(Encodable, ChannelPacket, abc.ABC):
    pass


class DecodablePacket(Decodable, ChannelPacket, abc.ABC):
    pass
