from log_manager import LogManager
import logging

from bluezero import peripheral, adapter

class BleService:

    def __init__(self, uuid: str, name: str):
        self.uuid = uuid
        self.name = name

    def __repr__(self):
        return f"{self.__class__.__name__} (uuid = {self.uuid}, name = {self.name})"


class BleChar(BleService):

    data:bytes

    def __read_cb() -> list[bytes]:
        return list(self.data)

    def __init__(self, uuid: str, name: str, read_data:bytes|str|None, notify_cb=None, write_cb=None):
        super().__init__(uuid, name) 

        if read_data is not None:
            if isinstance(read_data, str):
                self.data = read_data.encode("utf-8")
            else:
                self.data = read_data
            self.read_cb = self.__read_cb
        else:
            self.read_cb = None

        self.write_cb = write_cb
        self.notify_cb = notify_cb
        return


    def __repr__(self):
        return super().__repr__()


class PeripheralHandler():

    adapter_addr:str = None
    logger:logging.Logger = None
    periph:peripheral.Peripheral = None
    services:dict[int, BleService] = {}
    chars:dict[int, BleChar] = {}

    def __init__(self):

        self.logger = LogManager().get_logger(self.__class__.__name__)
        self.adapter_addr = list(adapter.Adapter.available())[0].address
        self.logger.debug(f"using local adapter: {self.adapter_addr}")

        self.periph = peripheral.Peripheral(
            adapter_address=self.adapter_addr,
            #local_name=MOBILE_NAME
        )

        return

    def add_service(self, service:BleService):
        count = len(self.services)

        self.periph.add_service(
            srv_id=count,
            uuid=service.uuid,
            primary=True
        )

        self.services[count] = service
        self.logger.info(f"service added as #{count} {service}")
        return

    def __calc_flags(self, char:BleChar) -> tuple[list, list]:
        check = [("read", char.read_cb), ("write", char.write_cb), ("notify", char.notify_cb)]
        flags = []
        for flag, func in check:
            if func is not None:
                flags.append(flag)
        if len(flags) == 0:
            raise Exception(f"Calculated empty flags for {char}. Config mistake?")
        return flags

    def add_char(self, service:BleService, char:BleChar):
        count = len(self.chars)
        found = False
        for id, s in self.services.items():
            if s == service:
                flags = self.__calc_flags(char)
                self.periph.add_characteristic(
                    srv_id=id,
                    chr_id=count,
                    uuid=char.uuid,
                    value=[],
                    notifying=False,
                    flags=flags,
                    read_callback=char.read_cb,
                    notify_callback=char.notify_cb,
                    write_callback=char.write_cb
                )
                found = True
                self.logger.info(f"char {char.name} added to service {s.name} (#{id}) with flags {' '.join(flags)}")
                break
        if not found:
            raise Exception(f"could not find a matching service for char {char}!")
        self.chars[count] = char
        return

    def set_on_connect(self, cb):
        self.periph.on_connect = cb
        return

    def set_on_disconnect(self, cb):
        self.periph.on_disconnect = cb
        return
    
    def publish(self):
        self.logger.warning("publishing BLE...")
        self.periph.publish()
        return