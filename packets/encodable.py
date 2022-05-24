import abc

from util import Buffer


class Decodable(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def from_buf(cls, buf: Buffer) -> 'Decodable':
        ...


class Encodable(abc.ABC):
    @abc.abstractmethod
    def to_buf(self) -> bytes:
        ...
