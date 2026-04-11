from datetime import datetime

from value_converter import ValueConverter


class ParseUtils():
    @staticmethod
    def consume(data: bytes, n: int) -> tuple[int, bytes]:
        # NOTE: copying this bytes object every time is rather wasteful
        assert n <= len(data)
        value = int.from_bytes(data[0:n], "little")
        return value, data[n:]

    @staticmethod
    def consume_u8(data: bytes) -> tuple[int, bytes]:
        value, data = __class__.consume(data, 1)
        return value, data

    @staticmethod
    def consume_u16(data: bytes) -> tuple[int, bytes]:
        value, data = __class__.consume(data, 2)
        return value, data

    @staticmethod
    def consume_u32(data: bytes) -> tuple[int, bytes]:
        value, data = __class__.consume(data, 4)
        return value, data

    @staticmethod
    def consume_i16(data: bytes) -> tuple[int, bytes]:
        value, data = __class__.consume(data, 2)
        value = ValueConverter.sign_extend(value, 16)
        return value, data

    @staticmethod
    def consume_f16(data: bytes) -> tuple[float, bytes]:
        value, data = __class__.consume(data, 2)
        value = ValueConverter.decode_medfloat16(value)
        return value, data

    @staticmethod
    def consume_f32(data: bytes) -> tuple[float, bytes]:
        value, data = __class__.consume(data, 4)
        value = ValueConverter.decode_medfloat32(value)
        return value, data

    @staticmethod
    def consume_datetime(data: bytes) -> tuple[datetime, bytes]:
        n = 7
        assert n <= len(data)
        value = ValueConverter.decode_datetime(data[0:n])
        return value, data[n:]

