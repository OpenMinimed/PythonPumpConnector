from value_converter import ValueConverter


class ParseUtils():
    @staticmethod
    def consume(data: bytes, n: int) -> tuple[int, bytes]:
        # NOTE: copying this bytes object every time is rather wasteful
        assert n <= len(data)
        value = int.from_bytes(data[0:n], "little")
        return value, data[n:]
