import logging
from abc import ABCMeta, abstractmethod
from datetime import datetime
from time import sleep
import atexit
from threading import Thread

from utils.log_manager import LogManager
from utils.os_utils import exec

from bluezero.device import Device


class Advertiser(metaclass=ABCMeta):
    adv_name:str = None
    log:logging.Logger = None
    instance_id:int = None
    adv_started:datetime|None = None
    sleep_delay:int = 0.5 # this needs to be very high, since it can SILENTLY DROP COMMANDS!!! debugging this was a fucking pain. state of linux bluetooth in 2026 everyone
    connected:bool = False
    fake_adv_time:int = 5 # in sec. this is passed down to the OS
    adv_thread_time:float = 4.9 # the real value we let the advertisement packets live

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
        "sudo btmgmt power on",
        # DOES NOT WORK, NEEDS CONFIG WORKAROUND!!!: "sudo btmgmt privacy device"
    ]

    def __init__(self, adv_name: str, instance_id: int = 1):
        """
        adv_name:    name for advertising
        instance_id: the bluez instance id
        """

        self.adv_name = adv_name
        self.instance_id = instance_id
        self.logger = LogManager.get_logger(self.__class__.__name__)

        # run btmgmt commands
        for c in self.startup_commands:
            exec(c)
            # wait for hci to actually perform it. NOTE: make this delay
            # larger if you see errors!
            sleep(self.sleep_delay)

        atexit.register(self.stop_adv) # just to be on the safe side
        self.logger.warning("always accept the pairing if your desktop environment asks for it!")
        return

    @abstractmethod
    def _create_adv_cmd(self) -> str:
        ...

    def __clear_adv(self):
        exec("sudo btmgmt clr-adv")
        return

    def stop_adv(self) -> None:
        self.logger.info("advertising stopped")

        # WARNING! This is a very hacky and deliberate almost-race-condition.
        # Don't change these two lines!
        self.adv_started = None
        self.__clear_adv()
        return

    def start_adv(self) -> None:
        if self.adv_started != None:
            self.logger.error(f"advertisement already running? skipping...")
            return
        self.adv_started = datetime.now()
        if self.adv_name:
            self.logger.info(f"advertisement started at {self.adv_started} as {self.adv_name}")
        else:
            self.logger.info(f"advertisement started at {self.adv_started} without a device name")
        thread = Thread(target = self.__adv_thread)
        thread.start()
        return

    def on_connect_cb(self, device:Device):
        self.logger.warning(f"device {device.address} connected!")
        self.connected = True
        self.stop_adv()
        # does not work: exec(f"bluetoothctl trust {device.address}") # auto accept it (skip gui check)
        return

    def on_disconnect_cb(self, device:Device):
        self.logger.warning(f"device {device.address} disconnected!")
        self.connected = False
        self.start_adv()
        return

    def __adv_thread(self):
        # hacky, since bluezero also starts an advertisement, which is not
        # good for us and we need to "fight it"
        while True:
            if self.adv_started == None:
                return
            cmd = self._create_adv_cmd()
            exec(cmd)
            sleep(self.adv_thread_time)
            self.__clear_adv()

