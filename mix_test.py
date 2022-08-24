def upmix(data: bytes, single_sample_size: int, source_channels: int, sink_channels: int) -> bytes:
    output = b""

    i = 0

    while i < len(data):
        for j in range(sink_channels):
            output += data[i:i + single_sample_size]
        i += (single_sample_size * source_channels)

    return output


upmixed = upmix(b"\xab\xcd\xef\x12\x34\x56", 2, 1, 3)
print(upmix(upmixed, 2, 3, 1).hex())
