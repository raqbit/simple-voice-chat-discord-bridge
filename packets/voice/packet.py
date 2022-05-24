import abc

from packets.encodable import Encodable, Decodable


class VoicePacket(abc.ABC):
    ID: int


class EncodableVoicePacket(Encodable, VoicePacket, abc.ABC):
    pass


class DecodableVoicePacket(Decodable, VoicePacket, abc.ABC):
    pass
