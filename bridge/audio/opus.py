import enum
from typing import Any, Optional

from opuslib import Encoder, APPLICATION_VOIP
from opuslib.api import decoder, ctl


class OpusDecoder:
    decoder_state: Any

    frame_size: int
    channels: int

    def __init__(self, sample_rate: int, frame_size: int, channels):
        self.frame_size = frame_size
        self.channels = channels
        self.decoder_state = decoder.create_state(sample_rate, channels)

    def __del__(self) -> None:
        if hasattr(self, 'decoder_state'):
            # Destroying state only if __init__ completed successfully
            decoder.destroy(self.decoder_state)

    def decode(self, data: bytes) -> bytes:
        # Java decoder feeds libopus null so that it can handle packet loss concealment (PLC)
        # https://github.com/henkelmax/simple-voice-chat/blob/cef95a1e8323e194f5f51ea18da248c8fab9c8dc/common/src/main/java/de/maxhenkel/voicechat/plugins/impl/opus/JavaOpusDecoderImpl.java#L45
        if data is None or len(data) == 0:
            return self._decode(None, 0)
        return self._decode(data, len(data))

    def _decode(self, opus_data: Optional[bytes], data_len: int) -> bytes:
        return decoder.decode(
            self.decoder_state,
            opus_data,
            data_len,
            self.frame_size,
            False,
            channels=self.channels
        )

    def reset(self):
        decoder.decoder_ctl(
            self.decoder_state,
            ctl.reset_state
        )

class EncodingApplication(enum.Enum):
    VOICE = APPLICATION_VOIP


class OpusEncoder:
    frame_size: int

    def __init__(self, sample_rate: int, frame_size: int, channels: int, application: EncodingApplication):
        self.frame_size = frame_size
        self.encoder = Encoder(sample_rate, channels, application.value)

    def encode(self, data: bytes) -> bytes:
        return self.encoder.encode(data, self.frame_size)

    def reset(self):
        self.encoder.reset_state()
