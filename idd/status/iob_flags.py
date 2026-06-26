from enum import IntEnum

class InsulinOnBoardResponseFlags(IntEnum):        
    REMAINING_DURATION_PRESENT = 1,
    IOB_PARTIAL_STATUS_PRESENT = 2,
