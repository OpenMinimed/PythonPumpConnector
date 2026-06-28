import datetime as dt

from utils.parse_utils import ParseUtils

from history.enums import (
    CL1TransitionState,
    InsulinDeliveryStoppedReason,
    InsulinDeliveryRestartedReason,
    RecordingReason,
)
from history.events.base import HistoryEventData


class CL1TransitionData(HistoryEventData):
    """Event data for the CL1 Transition event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.transition_state: int | None = None

    def _parse_impl(self, data):
        self.transition_state, data = ParseUtils.consume_u8(data)

        assert CL1TransitionState.contains_value(self.transition_state)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Transition State: {CL1TransitionState(self.transition_state).name}",
        ]) + "\n)"


class InsulinDeliveryStoppedData(HistoryEventData):
    """Event data for the Insulin Delivery Stopped event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.insulin_delivery_stopped_reason: int | None = None

    def _parse_impl(self, data):
        self.insulin_delivery_stopped_reason, data = ParseUtils.consume_u8(data)

        assert InsulinDeliveryStoppedReason.contains_value(self.insulin_delivery_stopped_reason)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Insulin Delivery Stopped Reason: {InsulinDeliveryStoppedReason(self.insulin_delivery_stopped_reason).name}",
        ]) + "\n)"


class InsulinDeliveryRestartedData(HistoryEventData):
    """Event data for the Insulin Delivery Restarted event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.insulin_delivery_restarted_reason: int | None = None

    def _parse_impl(self, data):
        self.insulin_delivery_restarted_reason, data = ParseUtils.consume_u8(data)

        assert InsulinDeliveryRestartedReason.contains_value(self.insulin_delivery_restarted_reason)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Insulin Delivery Restarted Reason: {InsulinDeliveryRestartedReason(self.insulin_delivery_restarted_reason).name}",
        ]) + "\n)"


class MealData(HistoryEventData):
    """Event data for the Meal event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.food_amount: float | None = None

    def _parse_impl(self, data):
        self.food_amount, data = ParseUtils.consume_f16(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Food Amount: {self.food_amount} g",
        ]) + "\n)"


class NGPReferenceTimeData(HistoryEventData):
    """Event data for the NGP Reference Time event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.recording_reason: int | None = None
        self.date_time: dt.datetime | None = None

    def _parse_impl(self, data):
        self.recording_reason, data = ParseUtils.consume_u8(data)
        self.date_time,        data = ParseUtils.consume_datetime(data)

        assert RecordingReason.contains_value(self.recording_reason)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Recording Reason: {RecordingReason(self.recording_reason).name}",
            f"Date Time:        {self.date_time}",
        ]) + "\n)"