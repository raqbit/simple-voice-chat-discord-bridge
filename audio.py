import queue
import struct
import threading
from functools import cached_property
from typing import Any, Optional, Callable

import opuslib.api.ctl
import opuslib.api.decoder
from opuslib import APPLICATION_VOIP

class OpusDecoder:
    decoder_state: Any

    frame_size: int
    channels: int

    def __init__(self, sample_rate: int, frame_size: int, channels):
        self.frame_size = frame_size
        self.channels = channels
        self.decoder_state = opuslib.api.decoder.create_state(sample_rate, channels)

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
            self.frame_size,
            False,
            channels=self.channels
        )

    def reset(self):
        opuslib.api.decoder.decoder_ctl(
            self.decoder_state,
            opuslib.api.ctl.reset_state
        )

class OpusEncoder:
    frame_size: int

    def __init__(self, sample_rate: int, frame_size: int, channels: int, application: str):
        self.frame_size = frame_size
        self.encoder = opuslib.Encoder(sample_rate, channels, application)

    def encode(self, data: bytes) -> bytes:
        return self.encoder.encode(data, self.frame_size)

    def reset(self):
        self.encoder.reset_state()

class AudioProcessThread(threading.Thread):
    _sample_rate: int
    _frame_length: int

    _input_queue: queue.Queue
    _should_decode_input: bool

    _decoder: OpusDecoder
    _encoder: OpusEncoder

    _single_sample_size = struct.calcsize("h")

    _source_channels: int

    _sink_channels: int
    _sink_callback: Callable[[bytes], None]

    _end_thread: threading.Event

    def __init__(
        self,
        sink_callback: Callable[[bytes], None],
        sample_rate: int,
        frame_length: int, # Frame length in milliseconds
        source_channels: int,
        sink_channels: int,
        decode=False
    ):
        super().__init__(name="AudioProcessThread")

        self._sample_rate = sample_rate
        self._frame_length = frame_length

        self._source_channels = source_channels

        self._sink_channels = sink_channels
        self._sink_callback = sink_callback

        self._should_decode_input = decode

        self._input_queue = queue.Queue()
        self._decoder = OpusDecoder(sample_rate, self._samples_per_frame, source_channels)

        self._encoder = OpusEncoder(sample_rate, self._samples_per_frame, sink_channels, APPLICATION_VOIP)

        self._end_thread = threading.Event()

    def enqueue(self, data: bytes):
        self._input_queue.put(data)

    def run(self) -> None:
        while not self._end_thread.is_set():
            try:
                to_encode = self._input_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # Decode opus audio if we need to
            if self._should_decode_input:
                to_encode = self._decoder.decode(to_encode)

            # Upmix or downmix decoded audio before encoding frame
            if self._source_channels != self._sink_channels:
                to_encode = self._mix(to_encode)

            # Encode frame
            result = self._encoder.encode(to_encode)

            # Send to sink
            self._sink_callback(result)

    def _mix(self, data: bytes) -> bytes:
        output = b""

        i = 0
        while i < len(data):
            for j in range(self._sink_channels):
                output += data[i:i + self._single_sample_size]
            i += (self._single_sample_size * self._source_channels)

        return output

    @cached_property
    def _samples_per_frame(self):
        return int(self._sample_rate / 1000 * self._frame_length)

    @cached_property
    def _source_sample_size(self):
        return self._single_sample_size * self._source_channels

    @cached_property
    def _sink_sample_size(self):
        return self._single_sample_size * self._sink_channels

    @cached_property
    def _source_frame_size(self):
        return self._samples_per_frame * self._source_sample_size

    @cached_property
    def _sink_frame_size(self):
        return self._samples_per_frame * self._sink_sample_size

    def print_info(self):
        print('\t========AudioProcessThread========')
        print(f'\tSample rate: {self._sample_rate}Hz\r')
        print(f'\tFrame length: {self._frame_length}ms')
        print(f'\tSamples/frame: {self._samples_per_frame} samples')

        print(f'\tSource channels: {self._source_channels}')
        print(f'\tSink channels: {self._sink_channels}')

        print(f'\tSource sample size: {self._source_sample_size} bytes')
        print(f'\tSink sample size: {self._sink_sample_size} bytes')

        print(f'\tSource frame size: {self._source_frame_size}')
        print(f'\tSink frame size: {self._sink_frame_size}')
        print('\t==================================')

    def stop(self):
        self._end_thread.set()
        super().join()
