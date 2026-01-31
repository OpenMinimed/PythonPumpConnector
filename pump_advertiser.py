import logging
from datetime import datetime
from time import sleep
import atexit
import subprocess
import re
from threading import Thread

from log_manager import LogManager
from utils import exec, gen_mobile_name

from bluezero.device import Device


class PumpAdvertiser():

    mobile_name:str = None
    log:logging.Logger = None
    instance_id:int = None
    adv_started:datetime|None = None
    sleep_delay:int = 0.5 # this needs to be very high, since it can SILENTLY DROP COMMANDS!!! debugging this was a fucking pain. state of linux bluetooth in 2026 everyone
    connected:bool = False
    adv_time:int = 5 # sec

    startup_commands:list[str] = [
        "sudo btmgmt power off",
        "sudo btmgmt bredr off",
        "sudo btmgmt le on",
        "sudo btmgmt sc off",
        "sudo btmgmt pairable on",
        "sudo btmgmt connectable on",
        "sudo btmgmt bondable on",
        "sudo btmgmt discov on",
        "sudo btmgmt io-cap 3", # this is very important!
        #"bluetoothctl agent NoInputNoOutput",
        "sudo btmgmt power on",
    ]

    def __init__(self, instance_id:int=1):
        """
        instance id is the bluez instance id
        """

        self.instance_id = instance_id
        self.logger = LogManager.get_logger(self.__class__.__name__)

        # gen a mobile name
        self.mobile_name = gen_mobile_name()
        #self.logger.info(f"generated mobile name: {self.mobile_name}")
        
        # run btmgmt commands
        for c in self.startup_commands:
            exec(c)
            sleep(self.sleep_delay) # wait for hci to actually perform it. NOTE: make this delay larger if you see errors!

        atexit.register(self.stop_adv) # just to be on the safe side
        self.logger.warning("always accept the pairing if your desktop environment asks for it!")

        return

    def __create_adv_cmd(self) -> str:

        data = "02 01 06 "  # flags - we have turned BR/EDR off
        data += f"12 FF F901 00 {self.mobile_name.encode().hex()} 00 "  # manufacturer data
        data += "02 0A 01 "  # tx power
        data += "03 03 82 FE "  # 16-bit service UUID

        data = data.replace(" ", "")

        # timeout is how long the bluez object lives (??)
        # set duration and timeout to the same for now

        full_cmd = f"sudo btmgmt add-adv -d {data} -t {self.adv_time} -D {self.adv_time} {self.instance_id}"
        return full_cmd

    def __clear_adv(self):
        exec("sudo btmgmt clr-adv")
        return

    def stop_adv(self) -> None:
        self.logger.info("advertising stopped")
        self.adv_started = None
        self.__clear_adv()
        return

    def start_adv(self) -> None:
        """
        time is in seconds
        """
        # for i in range(4):
        #     self.stop_adv() # start with clearing all, since we might have bluezero's in the list
        #     sleep(0.25)
        #sleep(2) # wait for things to normalize
        if self.adv_started != None:
            self.logger.error(f"advertisement already running? skipping...")
            return
        self.adv_started = datetime.now()
        self.logger.info(f"advertisement started at {self.adv_started} as {self.mobile_name}")
        thread = Thread(target = self.__adv_thread)
        thread.start()
        return

    def on_connect_cb(self, device:Device):
        self.logger.warning(f"device {device.address} connected!")
        self.connected = True
        self.stop_adv()
        return

    def on_disconnect_cb(self, device:Device):
        self.logger.warning(f"device {device.address} disconnected!")
        self.connected = False
        self.start_adv()
        return
    
    def __adv_thread(self):
        # hacky, since we bluezero also starts an advertisement, which is not good for us and we need to "fight it"
        while True:

            if self.adv_started == None:
                return
            
            cmd = self.__create_adv_cmd()
            exec(cmd)
            sleep(self.adv_time)
            self.__clear_adv()

    def __get_advertisement_count(self):
        result = subprocess.run(
            ["sudo", "btmgmt", "advinfo"],
            capture_output=True,
            text=True,
            check=True,
        )

        match = re.search(r"Instances list with (\d+) item", result.stdout)
        if not match:
            raise RuntimeError(f"Could not find advertisement count in: {result.stdout}")

        return int(match.group(1))
