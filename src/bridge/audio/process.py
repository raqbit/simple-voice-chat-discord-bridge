import queue
import struct
import threading
from collections.abc import Callable
from functools import cached_property

from bridge.audio.opus import EncodingApplication, OpusDecoder, OpusEncoder


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

        self._encoder = OpusEncoder(sample_rate, self._samples_per_frame, sink_channels, EncodingApplication.VOICE)

        self._end_thread = threading.Event()

    def enqueue(self, data: bytes):
        self._input_queue.put(data)

    def run(self) -> None:
        while not self._end_thread.is_set():
            try:
                to_encode = self._input_queue.get(timeout=0.1)
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
