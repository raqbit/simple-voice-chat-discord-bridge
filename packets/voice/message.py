import os
import uuid

from cryptography.hazmat.primitives.ciphers import modes, algorithms, Cipher

from util import Buffer


class InvalidSecretException(Exception):
    pass


# FIXME: these should just be functions and not class methods
class NetworkMessage:
    @classmethod
    def from_buf(cls, buf: Buffer, secret: uuid.UUID) -> 'Buffer':
        payload = Buffer(cls._decrypt_payload(buf.read(), secret))

        given_secret = payload.unpack_uuid()

        if given_secret != secret:
            raise InvalidSecretException("secret does not match expected")

        return payload

    @classmethod
    def from_client_buf(cls, buf: Buffer, secret: uuid.UUID) -> 'Buffer':
        buf.unpack_uuid()
        payload_len = buf.unpack_varint()

        enc_payload = Buffer(buf.read(payload_len))

        return cls.from_buf(enc_payload, secret)

    @classmethod
    def _decrypt_payload(cls, payload: bytes, secret: uuid.UUID) -> bytes:
        iv = payload[0:16]
        enc_payload = payload[16:]

        cipher = Cipher(algorithms.AES(secret.bytes), modes.CBC(iv))

        decryptor = cipher.decryptor()
        return decryptor.update(enc_payload) + decryptor.finalize()

    @classmethod
    def _encrypt_payload(cls, payload: bytes, secret: uuid.UUID) -> bytes:
        # Generate random IV
        iv = os.getrandom(16)

        cipher = Cipher(algorithms.AES(secret.bytes), modes.CBC(iv))
        encryptor = cipher.encryptor()

        # Encrypt payload
        encrypted_payload = encryptor.update(payload) + encryptor.finalize()

        return iv + encrypted_payload

    @classmethod
    def to_buf(cls, packet_id: int, payload: bytes, secret: uuid.UUID) -> bytes:
        buf = b""

        buf += Buffer.pack_string(secret)
        buf += Buffer.pack("c", packet_id)
        buf += Buffer.add(payload)

        return cls._encrypt_payload(buf, secret)

    @classmethod
    def to_server_buf(cls, packet_id: int, payload: bytes, sender: uuid.UUID, secret: uuid.UUID) -> bytes:
        buf = b""

        buf += Buffer.pack_uuid(sender)

        enc_payload = cls.to_buf(packet_id, payload, secret)
        buf += Buffer.pack_varint(len(enc_payload))
        buf += enc_payload

        return buf
