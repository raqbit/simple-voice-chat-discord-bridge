import abc

import quarry.types.buffer

Buffer = quarry.types.buffer.Buffer1_14

class Decodable(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def from_buf(cls, buf: Buffer) -> 'Decodable':
        ...


class Encodable(abc.ABC):
    @abc.abstractmethod
    def to_buf(self) -> bytes:
        ...
