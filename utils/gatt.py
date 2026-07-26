import time

from bluezero import dbus_tools

from utils.log_manager import LogManager
from utils.uuids import UUID


class GATTBase:
    def __init__(self):
        self.logger = LogManager.get_logger(self.__class__.__name__)

    def _add_char(self, uuid_service: UUID, uuid_char: UUID, flags, callback=None, start_notify=True, name=None):
        # use UUID enum member name if no custom name is given
        if name is None:
            assert uuid_char in UUID._value2member_map_
            name = UUID(uuid_char).name

        try:
            self.logger.info(f"Adding characteristic {name}")
            chrc = self.central.add_characteristic(uuid_service, uuid_char)
            while not chrc.resolve_gatt():
                time.sleep(0.2)
            assert set(flags).issubset(dbus_tools.dbus_to_python(chrc.flags))
            if callback is not None:
                chrc.add_characteristic_cb(callback)
                if start_notify:
                    chrc.start_notify()
            return chrc
        except Exception as e:
            self.logger.error(f"Failed to add characteristic {name}")
            self.logger.error(e)
            return None

