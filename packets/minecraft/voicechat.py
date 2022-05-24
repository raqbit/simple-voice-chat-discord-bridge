import uuid
from dataclasses import dataclass
from typing import Optional, Dict

from packets.encodable import Decodable, EncodablePacket, DecodablePacket
from util import Buffer

NAMESPACE = "voicechat"


@dataclass
class RequestSecretPacket(EncodablePacket, DecodablePacket):
    CHANNEL = f"{NAMESPACE}:request_secret"

    compat_version: int

    def to_buf(self) -> bytes:
        return Buffer.pack("i", self.compat_version)

    @classmethod
    def from_buf(cls, buf: Buffer) -> "RequestSecretPacket":
        compat_version = buf.unpack("i")

        return cls(
            compat_version=compat_version
        )


@dataclass
class SecretPacket(DecodablePacket):
    CHANNEL = f"{NAMESPACE}:secret"

    secret: uuid.UUID
    port: int
    player: uuid.UUID
    codec: int
    mtu: int
    dist: float
    fade_dist: float
    crouch_dist: float
    whisper_dist: float
    keep_alive: int
    groups_enabled: bool
    host: str
    allow_recording: bool

    @classmethod
    def from_buf(cls, buff: Buffer) -> "SecretPacket":
        secret = buff.unpack_uuid()
        port = buff.unpack("i")
        player = buff.unpack_uuid()
        codec = buff.read(1)[0]
        mtu = buff.unpack("i")
        dist = buff.unpack("d")
        fade_dist = buff.unpack("d")
        crouch_dist = buff.unpack("d")
        whisper_dist = buff.unpack("d")
        keep_alive = buff.unpack("i")
        groups_enabled = buff.unpack("?")
        host = buff.unpack_string()
        allow_recording = buff.unpack("?")

        return cls(
            secret=secret,
            port=port,
            player=player,
            codec=codec,
            mtu=mtu,
            dist=dist,
            fade_dist=fade_dist,
            crouch_dist=crouch_dist,
            whisper_dist=whisper_dist,
            keep_alive=keep_alive,
            groups_enabled=groups_enabled,
            host=host,
            allow_recording=allow_recording,
        )


@dataclass
class ClientGroup(Decodable):
    id: uuid.UUID
    name: str
    has_password: bool

    @classmethod
    def from_buf(cls, buf: Buffer) -> "ClientGroup":
        identifier = buf.unpack_uuid()
        name = buf.unpack_string()
        has_password = buf.unpack("?")
        return cls(
            id=identifier,
            name=name,
            has_password=has_password
        )


@dataclass
class PlayerState(Decodable):
    uuid: uuid.UUID
    name: str
    disabled: bool
    disconnected: bool
    group: Optional[ClientGroup]

    @classmethod
    def from_buf(cls, buf: Buffer) -> "PlayerState":
        disabled = buf.unpack("?")
        disconnected = buf.unpack("?")
        player_uuid = buf.unpack_uuid()
        name = buf.unpack_string()

        group = None
        if buf.unpack("?"):
            group = ClientGroup.from_buf(buf)

        return cls(
            uuid=player_uuid,
            name=name,
            disabled=disabled,
            disconnected=disconnected,
            group=group
        )


@dataclass
class UpdateStatePacket(EncodablePacket, DecodablePacket):
    CHANNEL = f"{NAMESPACE}:update_state"

    disconnected: bool
    disabled: bool

    def to_buf(self):
        return Buffer.pack("??", self.disconnected, self.disabled)

    @classmethod
    def from_buf(cls, buf: Buffer) -> "UpdateStatePacket":
        disconnected = buf.unpack("?")
        disabled = buf.unpack("?")

        return cls(
            disconnected=disconnected,
            disabled=disabled
        )


@dataclass
class PlayerStatePacket(DecodablePacket):
    CHANNEL = f"{NAMESPACE}:player_state"

    state: PlayerState

    @classmethod
    def from_buf(cls, buf: Buffer) -> "PlayerStatePacket":
        state = PlayerState.from_buf(buf)

        return cls(
            state=state,
        )


@dataclass
class PlayerStatesPacket(DecodablePacket):
    CHANNEL = f"{NAMESPACE}:player_states"

    states: Dict[uuid.UUID, PlayerState]

    @classmethod
    def from_buf(cls, buf: Buffer) -> "PlayerStatesPacket":
        states = {}

        count = buf.unpack("i")

        for i in range(count):
            state = PlayerState.from_buf(buf)
            states[state.uuid] = state

        return cls(
            states=states,
        )


@dataclass
class CreateGroupPacket(EncodablePacket, DecodablePacket):
    CHANNEL = f"{NAMESPACE}:create_group"

    name: str
    password: Optional[str]

    def to_buf(self) -> bytes:
        buf = Buffer.pack_string(self.name)

        has_password = self.password is not None
        buf += Buffer.pack("?", has_password)

        if has_password:
            buf += Buffer.pack_string(self.password)

        return buf

    @classmethod
    def from_buf(cls, buf: Buffer) -> "CreateGroupPacket":
        name = buf.unpack_string()

        password = None
        if buf.unpack("?"):
            password = buf.unpack_string()

        return cls(
            name=name,
            password=password
        )


@dataclass
class JoinGroupPacket(EncodablePacket, DecodablePacket):
    CHANNEL = f"{NAMESPACE}:set_group"

    group: uuid.UUID
    password: Optional[str]

    def to_buf(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_buf(cls, buf: Buffer) -> "JoinGroupPacket":
        group = buf.unpack_uuid()

        password = None
        if buf.unpack("?"):
            password = buf.unpack_string()

        return cls(
            group=group,
            password=password
        )


@dataclass
class LeaveGroupPacket(EncodablePacket, DecodablePacket):
    CHANNEL = f"{NAMESPACE}:leave_group"

    def to_buf(self) -> bytes:
        pass

    @classmethod
    def from_buf(cls, buf: Buffer) -> 'Decodable':
        pass


@dataclass
class JoinedGroupPacket(DecodablePacket):
    CHANNEL = f"{NAMESPACE}:joined_group"

    group: Optional[ClientGroup]
    wrong_password: bool

    @classmethod
    def from_buf(cls, buf: Buffer) -> "JoinedGroupPacket":
        group = None
        if buf.unpack("?"):
            group = ClientGroup.from_buf(buf)

        wrong_password = buf.unpack("?")

        return cls(
            group=group,
            wrong_password=wrong_password
        )
