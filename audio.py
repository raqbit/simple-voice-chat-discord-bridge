from typing import Any, Optional

import opuslib.api.ctl
import opuslib.api.decoder

_SAMPLE_RATE = 48000
_FRAME_SIZE = int((_SAMPLE_RATE / 1000) * 20)


class VoiceChatAudioDecoder:
    decoder_state: Any

    def __init__(self):
        self.decoder_state = opuslib.api.decoder.create_state(_SAMPLE_RATE, 1)

    def __del__(self) -> None:
        if hasattr(self, 'decoder_state'):
            # Destroying state only if __init__ completed successfully
            opuslib.api.decoder.destroy(self.decoder_state)

    def decode(self, data: bytes) -> bytes:
        # Java decoder feeds libopus null so that it can handle packet loss concealment (PLC)
        # https://github.com/henkelmax/simple-voice-chat/blob/cef95a1e8323e194f5f51ea18da248c8fab9c8dc/common/src/main/java/de/maxhenkel/voicechat/plugins/impl/opus/JavaOpusDecoderImpl.java#L45
        if data is None or len(data) == 0:
            return self._decode(None, 0)
        return self._decode(data, len(data))

    def _decode(self, opus_data: Optional[bytes], data_len: int) -> bytes:
        return opuslib.api.decoder.decode(
            self.decoder_state,
            opus_data,
            data_len,
            _FRAME_SIZE,
            False,
            channels=1
        )

    def reset(self):
        opuslib.api.decoder.decoder_ctl(
            self.decoder_state,
            opuslib.api.ctl.reset_state
        )


class VoiceChatAudioEncoder:
    def __init(self, application: str):
        self.encoder = opuslib.Encoder(_SAMPLE_RATE, 1, application)

    def encode(self, data: bytes) -> bytes:
        return self.encoder.encode(data, _FRAME_SIZE)

    def reset(self):
        self.encoder.reset_state()
