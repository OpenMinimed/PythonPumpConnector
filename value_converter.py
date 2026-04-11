import crc

from datetime import datetime


class ValueConverter():
    
    @staticmethod
    def decode_medfloat16(value) -> float:
        e = (value & 0xf000) >> 12
        m = (value & 0x0fff)
        if e & 0x8:
            e = e - 0x10
        if m & 0x800:
            m = m - 0x1000
        return float(m * 10**e)

    @staticmethod
    def decode_medfloat32(value):
        e = (value & 0xff000000) >> 24
        m = (value & 0x00ffffff)
        if e & 0x80:
            e = e - 0x100
        if m & 0x800000:
            m = m - 0x1000000
        return m * 10**e

    @staticmethod
    def decode_datetime(data: bytes):
        assert len(data) == 7, \
            "Expected date time to by exactly 7 bytes"
        return datetime(
            int.from_bytes(data[0:2], "little"), data[2], data[3],
            data[4], data[5], data[6]
        )

    @staticmethod
    def mgdl_to_mmolL(value_mgdl:float) -> float:
        molar_mass = 180.156
        return round((value_mgdl * 10) / molar_mass, 1)

    @staticmethod
    def kgl_to_mgdl(value_kgl: float) -> float:
        return 1e5 * value_kgl

    @staticmethod
    def e2e_crc(data: bytes) -> int:

        calc = crc.Calculator(crc.Configuration(
            width=16,
            polynomial=0x1021,
            init_value=0xffff,
            final_xor_value=0,
            reverse_input=False,
            reverse_output=False,
        ))
        return calc.checksum(data)
    
    @staticmethod
    def check_crc(msg:bytes) -> bool:
        data = msg[0:-2]
        crc_rcv = msg[-2:]
        crc_calculated = ValueConverter.e2e_crc(data)
        crc_rcv = int.from_bytes(crc_rcv, byteorder="little")
        return crc_rcv == crc_calculated

    @staticmethod
    def sign_extend(value:int, bits=8) -> int:
        sign_bit = 1 << (bits - 1)
        return value - (1 << bits) if value & sign_bit else value
    

if __name__ == "__main__":

    print(ValueConverter.check_crc(bytes.fromhex("ea07031c0a1f2a80ff0873")))

    
