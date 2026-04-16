from enum import IntEnum

class BaseEnum(IntEnum):
    @classmethod
    def contains_value(cls, v):
        return v in cls._value2member_map_

