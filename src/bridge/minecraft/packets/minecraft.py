from dataclasses import dataclass

from bridge.util.encodable import Buffer, Decodable

NAMESPACE = "minecraft"


@dataclass
class RegisterPacket(Decodable):
    CHANNEL = f"{NAMESPACE}:register"

    channels: list[str]

    def to_buf(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_buf(cls, buf: Buffer) -> RegisterPacket:
        data = buf.read()

        channels = []

        segments = data.split(b"\x00")

        for chan in segments[:len(segments) - 1]:
            channels.append(chan.decode("utf-8"))

        return cls(
            channels=channels
        )


@dataclass
class BrandPacket(Decodable):
    CHANNEL = f"{NAMESPACE}:brand"

    brand: str

    def to_buf(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_buf(cls, buf: Buffer) -> BrandPacket:
        brand = buf.unpack_string()

        return cls(brand=brand)
