import os
import time
import uuid


def uuid7() -> uuid.UUID:
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)

    b = bytearray(16)
    b[0:6] = ts_ms.to_bytes(6, "big")
    b[6] = 0x70 | ((rand_a >> 8) & 0x0F)
    b[7] = rand_a & 0xFF
    rb = rand_b.to_bytes(8, "big")
    b[8] = (rb[0] & 0x3F) | 0x80
    b[9:16] = rb[1:8]
    return uuid.UUID(bytes=bytes(b))

