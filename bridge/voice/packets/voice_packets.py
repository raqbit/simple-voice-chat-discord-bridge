import uuid
from dataclasses import dataclass
from typing import NamedTuple

from bridge.voice.packets.packet import DecodableVoicePacket, EncodableVoicePacket
from bridge.util.encodable import Buffer


@dataclass
class MicPacket(EncodableVoicePacket, DecodableVoicePacket):
    ID = 0x01

    data: bytes
    whispering: bool
    sequence: int

    def to_buf(self) -> bytes:
        return Buffer.pack_varint(len(self.data)) + self.data + \
               Buffer.pack("q?", self.sequence, self.whispering)

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'MicPacket':
        data_len = buf.unpack_varint()
        data = buf.read(data_len)
        (sequence, whispering) = buf.unpack("q?")

        return cls(
            data=data,
            sequence=sequence,
            whispering=whispering
        )


@dataclass
class SoundPacket:
    sender: uuid.UUID
    data: bytes
    sequence: int


@dataclass
class PlayerSoundPacket(SoundPacket, DecodableVoicePacket):
    ID = 0x02

    whispering: bool

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'PlayerSoundPacket':
        sender = buf.unpack_uuid()
        data_len = buf.unpack_varint()
        data = buf.read(data_len)
        (sequence, whispering) = buf.unpack("q?")

        return cls(
            sender=sender,
            data=data,
            sequence=sequence,
            whispering=whispering
        )


@dataclass
class GroupSoundPacket(SoundPacket, DecodableVoicePacket):
    ID = 0x03

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'GroupSoundPacket':
        sender = buf.unpack_uuid()
        data_len = buf.unpack_varint()
        data = buf.read(data_len)
        sequence = buf.unpack("q")

        return cls(
            sender=sender,
            data=data,
            sequence=sequence,
        )


class Location(NamedTuple):
    x: float
    y: float
    z: float

    def __str__(self):
        return f"({self.x}, {self.y}, {self.z})"


@dataclass
class LocationSoundPacket(SoundPacket, DecodableVoicePacket):
    ID = 0x04

    location: Location

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'LocationSoundPacket':
        sender = buf.unpack_uuid()
        location = Location(*buf.unpack("ddd"))
        data_len = buf.unpack_varint()
        data = buf.read(data_len)
        sequence = buf.unpack("q")

        return cls(
            sender=sender,
            location=location,
            data=data,
            sequence=sequence,
        )


@dataclass
class AuthenticatePacket(EncodableVoicePacket, DecodableVoicePacket):
    ID = 0x05

    player_uuid: uuid.UUID
    secret: uuid.UUID

    def to_buf(self) -> bytes:
        return Buffer.pack_uuid(self.player_uuid) + \
               Buffer.pack_uuid(self.secret)

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'AuthenticatePacket':
        player_uuid = buf.unpack_uuid()
        secret = buf.unpack_uuid()

        return cls(
            player_uuid=player_uuid,
            secret=secret
        )


@dataclass
class AuthenticateAckPacket(DecodableVoicePacket):
    ID = 0x06

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'AuthenticateAckPacket':
        return cls()


@dataclass
class PingPacket(EncodableVoicePacket, DecodableVoicePacket):
    ID = 0x07

    id: uuid.UUID
    timestamp: int

    def to_buf(self) -> bytes:
        return Buffer.pack_uuid(self.id) + Buffer.pack("q", self.timestamp)

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'PingPacket':
        ping_id = buf.unpack_uuid()
        timestamp = buf.unpack("q")

        return cls(
            id=ping_id,
            timestamp=timestamp
        )


@dataclass
class KeepAlivePacket(EncodableVoicePacket):
    ID = 0x08

    def to_buf(self) -> bytes:
        return b""
