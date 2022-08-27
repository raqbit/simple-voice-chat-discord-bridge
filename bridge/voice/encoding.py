import os
import uuid

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import modes, algorithms, Cipher

from bridge.util.encodable import Buffer


class InvalidSecretException(Exception):
    pass


class UnknownSenderException(Exception):
    pass


_pkcs5 = padding.PKCS7(128)


def decode_voice_packet(buf: Buffer, secret: uuid.UUID) -> Buffer:
    payload = Buffer(_decrypt_payload(buf.read(), secret))

    given_secret = payload.unpack_uuid()

    if given_secret != secret:
        raise InvalidSecretException("secret does not match expected")

    return payload


def decode_client_sent_voice_packet(buf: Buffer, secrets: dict[uuid.UUID, uuid.UUID]) -> (uuid.UUID, Buffer):
    sender = buf.unpack_uuid()
    payload_len = buf.unpack_varint()

    secret = secrets[sender]

    if sender not in secrets:
        raise UnknownSenderException("received packet by unknown sender")

    enc_payload = Buffer(buf.read(payload_len))

    return sender, decode_voice_packet(enc_payload, secret)


def encode_voice_packet(packet_id: int, payload: bytes, secret: uuid.UUID) -> bytes:
    buf = b""

    buf += Buffer.pack_uuid(secret)
    buf += Buffer.pack("c", packet_id.to_bytes(1, "big"))
    buf += payload

    return _encrypt_payload(buf, secret)


def encode_client_sent_voice_packet(packet_id: int, sender: uuid.UUID, payload: bytes, secret: uuid.UUID):
    buf = b""

    buf += Buffer.pack_uuid(sender)

    enc_payload = encode_voice_packet(packet_id, payload, secret)
    buf += Buffer.pack_varint(len(enc_payload))
    buf += enc_payload

    return buf


iv_size = 16


def _decrypt_payload(data: bytes, secret: uuid.UUID) -> bytes:
    iv = data[0:iv_size]
    enc_payload = data[iv_size:]

    cipher = Cipher(algorithms.AES(secret.bytes), modes.CBC(iv))

    decryptor = cipher.decryptor()
    padded_payload = decryptor.update(enc_payload) + decryptor.finalize()

    unpadder = _pkcs5.unpadder()

    return unpadder.update(padded_payload) + unpadder.finalize()


def _encrypt_payload(data: bytes, secret: uuid.UUID) -> bytes:
    padder = _pkcs5.padder()

    padded_data = padder.update(data) + padder.finalize()

    # Generate random IV
    iv = os.getrandom(iv_size)

    cipher = Cipher(algorithms.AES(secret.bytes), modes.CBC(iv))
    encryptor = cipher.encryptor()

    # Encrypt payload
    encrypted_payload = encryptor.update(padded_data) + encryptor.finalize()

    return iv + encrypted_payload
