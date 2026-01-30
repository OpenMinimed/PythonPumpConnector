import logging
from datetime import datetime
from time import sleep
import atexit

from log_manager import LogManager
from utils import exec, gen_mobile_name

from bluezero.device import Device


class PumpAdvertiser():

    mobile_name:str = None
    log:logging.Logger = None
    instance_id:int = None
    adv_started:datetime|None = None
    sleep_delay:int=0.15
    connected:bool = False

    startup_commands:list[str] = [
        "sudo btmgmt power off",
        "sudo btmgmt bredr off",
        "sudo btmgmt le on",
        "sudo btmgmt sc off",
        "sudo btmgmt io-cap 3", # this is very important!
        "sudo btmgmt power on"
    ]

    def __init__(self, instance_id:int=1):
        """
        instance id is the bluez instance id
        """

        self.instance_id = instance_id
        self.logger = LogManager.get_logger(self.__class__.__name__)

        # gen a mobile name
        self.mobile_name = gen_mobile_name()
        self.logger.info(f"generated mobile name: {self.mobile_name}")
        
        # run btmgmt commands
        for c in self.startup_commands:
            exec(c)
            sleep(self.sleep_delay) # wait for hci to actually perform it. NOTE: make this delay larger if you see errors!

        atexit.register(self.stop_adv) # just to be on the safe side
        self.logger.warning("always accept the pairing if your desktop environment asks for it!")

        return

    def __create_adv_cmd(self, time) -> str:

        data = "02 01 06 "  # flags - we have turned BR/EDR off
        data += f"12 FF F901 00 {self.mobile_name.encode().hex()} 00 "  # manufacturer data
        data += "02 0A 01 "  # tx power
        data += "03 03 82 FE "  # 16-bit service UUID

        data = data.replace(" ", "")

        # timeout is how long the bluez object lives (??)
        # set duration and timeout to the same for now

        full_cmd = f"sudo btmgmt add-adv -d {data} -t {time} -D {time} {self.instance_id}"
        return full_cmd

    def stop_adv(self) -> None:
        exec("sudo btmgmt clr-adv")
        self.logger.info("advertising stopped")
        self.adv_started = None
        return

    def start_adv(self, duration:int=360) -> None:
        """
        time is in seconds
        """
        cmd = self.__create_adv_cmd(duration)
        exec(cmd)
        self.adv_started = datetime.now()
        self.logger.info(f"advertisement started at {self.adv_started}")
        return

    def on_connect_cb(self, device:Device):
        self.logger.info(f"device {dev.address} connected!")
        self.connected = True
        self.stop_adv()
        return

    def on_disconnect_cb(device:Device):
        self.logger.warning(f"device {dev.address} disconnected!")
        self.connected = False
        self.start_adv()
        return