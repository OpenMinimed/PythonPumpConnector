from log_manager import LogManager

class SakeHandler():
    
    pump_enabled:bool = False
    char=None

    def __init__(self):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        return

    def notify_callback(self, is_notifying:bool, char):
        if is_notifying and not self.pump_enabled:
            self.logger.warning("pump wants to be friends with us!")
            self.pump_enabled = True
            self.__send(bytes(20))

        if is_notifying == False:
            self.pump_enabled = False
            self.logger.error(f"pump disabled notifications!")

        self.logger.info(f"sake notify data received")
        return

    def write_callback(self, value:bytearray, options:dict):
        """
        options has fields: device, link, mtu
        """
        value = bytes(value)
        self.logger.info(f"sake write callback received: {value.hex()}, {options}")
        return

    def set_char(self, char):
        self.char = char
        return

    def __send(self, data:bytes):
        if self.char is None:
            raise RuntimeError(f"Sake char is none! You forgot to call set_char()!")
        self.char.set_value(list(data)) # TODO: threading bug!!!! fix it
        self.logger.info(f"sent data on sake port: {data.hex()}")
        return