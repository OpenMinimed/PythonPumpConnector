

class ValueConverter():
    
    @staticmethod
    def as_f16(value) -> float:
        e = (value & 0xf000) >> 12
        m = (value & 0x0fff)
        if e & 0x8:
            e = e - 0x10
        if m & 0x800:
            m = m - 0x1000
        return float(m * 10**e)
    
    @staticmethod
    def mgdl_to_mmolL(value_mgdl:float) -> float:
        molar_mass = 180.156
        return round((value_mgdl * 10) / molar_mass, 1)
