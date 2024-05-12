from __future__ import annotations

import uuid
from dataclasses import dataclass

from bridge.util.encodable import Buffer
from bridge.voice.packets import Decodable
from .packet import DecodablePacket, EncodablePacket

NAMESPACE = "voicechat"


@dataclass
class RequestSecretPacket(EncodablePacket, DecodablePacket):
    CHANNEL = f"{NAMESPACE}:request_secret"

    compat_version: int

    def to_buf(self) -> bytes:
        return Buffer.pack("i", self.compat_version)

    @classmethod
    def from_buf(cls, buf: Buffer) -> RequestSecretPacket:
        compat_version = buf.unpack("i")

        return cls(
            compat_version=compat_version
        )


@dataclass
class SecretPacket(EncodablePacket, DecodablePacket):
    CHANNEL = f"{NAMESPACE}:secret"

    secret: uuid.UUID
    port: int
    player: uuid.UUID
    codec: bytes
    mtu: int
    dist: float
    fade_dist: float
    crouch_dist: float
    whisper_dist: float
    keep_alive: int
    groups_enabled: bool
    host: str
    allow_recording: bool

    def to_buf(self) -> bytes:
        return Buffer.pack_uuid(self.secret) + \
            Buffer.pack("i", self.port) + \
            Buffer.pack_uuid(self.player) + \
            Buffer.pack(
                "ciddddi?", self.codec, self.mtu, self.dist, self.fade_dist, self.crouch_dist,
                self.whisper_dist, self.keep_alive, self.groups_enabled
            ) + \
            Buffer.pack_string(self.host) + \
            Buffer.pack("?", self.allow_recording)

    @classmethod
    def from_buf(cls, buff: Buffer) -> SecretPacket:
        secret = buff.unpack_uuid()
        port = buff.unpack("i")
        player = buff.unpack_uuid()
        (codec,
         mtu,
         dist,
         fade_dist,
         crouch_dist,
         whisper_dist,
         keep_alive,
         groups_enabled) = buff.unpack("ciddddi?")
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
    def from_buf(cls, buf: Buffer) -> ClientGroup:
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
    group: ClientGroup | None

    @classmethod
    def from_buf(cls, buf: Buffer) -> PlayerState:
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
    def from_buf(cls, buf: Buffer) -> UpdateStatePacket:
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
    def from_buf(cls, buf: Buffer) -> PlayerStatePacket:
        state = PlayerState.from_buf(buf)

        return cls(
            state=state,
        )


@dataclass
class PlayerStatesPacket(DecodablePacket):
    CHANNEL = f"{NAMESPACE}:player_states"

    states: dict[uuid.UUID, PlayerState]

    @classmethod
    def from_buf(cls, buf: Buffer) -> PlayerStatesPacket:
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
    password: str | None

    def to_buf(self) -> bytes:
        buf = Buffer.pack_string(self.name)

        has_password = self.password is not None
        buf += Buffer.pack("?", has_password)

        if has_password:
            buf += Buffer.pack_string(self.password)

        return buf

    @classmethod
    def from_buf(cls, buf: Buffer) -> CreateGroupPacket:
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
    password: str | None

    def to_buf(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_buf(cls, buf: Buffer) -> JoinGroupPacket:
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
        return b""

    @classmethod
    def from_buf(cls, buf: Buffer) -> LeaveGroupPacket:
        return cls()


@dataclass
class JoinedGroupPacket(DecodablePacket):
    CHANNEL = f"{NAMESPACE}:joined_group"

    group: ClientGroup | None
    wrong_password: bool

    @classmethod
    def from_buf(cls, buf: Buffer) -> JoinedGroupPacket:
        group = None
        if buf.unpack("?"):
            group = ClientGroup.from_buf(buf)

        wrong_password = buf.unpack("?")

        return cls(
            group=group,
            wrong_password=wrong_password
        )
