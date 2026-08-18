import re
import subprocess

from ble.advertiser import Advertiser
from utils.log_manager import LogManager
from utils.os_utils import exec


class MobileAdvertiser(Advertiser):
    already_paired: bool

    def __init__(self, adv_name: str, already_paired: bool = False):
        """
        adv_name:       device name used in advertising
        already_paired: whether we are trying to reconnect to an already paired pump
        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.already_paired = already_paired

        if already_paired:
            # it's helpful because we clear the default bluezero advertismeent
            # more often
            self.adv_thread_time = 1.0
            if not self.__check_kernel_workaround_applied():
                if not self.__is_kernel_locked_down():
                    self.__set_kernel_fix()
                else:
                    # userland workaround if we can not use the kernel level
                    # fix. if we spam the commands, we can get down under the
                    # 1s default advertising interval without any extra effort
                    self.adv_thread_time = 0.05 

        if already_paired:
            # NOTE: the pump ignores the advertising name for reconnects
            adv_name = None
        else:
            # NOTE: the pump only accepts advertisers with a specific naming scheme
            adv_name = "Mobile " + adv_name
            if not self.__is_valid_adv_name(adv_name):
                raise Exception(f"Invalid advertising name given: {adv_name}")

        super().__init__(adv_name)

    def _create_adv_cmd(self) -> str:
        data = ""

        # Flags: we have turned BR/EDR off in self.startup_commands
        data += "02 01 06"

        # 16-bit Service Class UUIDs: SAKE
        data += "03 03 "
        data += "81 fe" if self.already_paired else "82 fe"

        # Device Name
        if self.adv_name is not None:
            length = 1 + len(self.adv_name)
            data += f"{length:02x} 09 {self.adv_name.encode().hex()}"

        data = data.replace(" ", "")

        # timeout is how long the bluez object lives (??)
        # set duration and timeout to the same for now, idk

        full_cmd = f"sudo btmgmt add-adv -d {data} -t {self.fake_adv_time} -D {self.fake_adv_time} {self.instance_id}"
        return full_cmd

    def __is_valid_adv_name(self, s: str) -> bool:
        return bool(re.fullmatch(r"Mobile .{0,7}", s))

    def __is_kernel_locked_down(self) -> bool:
        locked = True
        with open("/sys/kernel/security/lockdown", "r") as f:
            for f in f.readlines():
                if "[none]" in f:
                    locked = False
                    break

        self.logger.info(f"kernel is locked down? {locked}")
        return locked

    def __check_kernel_workaround_applied(self) -> bool:
        paths = [
            '/sys/kernel/debug/bluetooth/hci0/adv_min_interval',
            '/sys/kernel/debug/bluetooth/hci0/adv_max_interval'
        ]
        for p in paths:
            result = subprocess.run(
                ["sudo", "cat", p],
                capture_output=True,
                text=True,
                check=True
            )
            result = result.stdout.strip()
            result = int(result)
            if result > 100:
                self.logger.warning("kernel level interval fix is NOT applied!")
                return False
        self.logger.info("kernel level interval fix is already applied!")
        return True

    def __set_kernel_fix(self) -> None:
        self.logger.info(f"applying kernel level fix...")
        exec("echo 50 | sudo tee /sys/kernel/debug/bluetooth/hci0/adv_min_interval")
        exec("echo 60 | sudo tee /sys/kernel/debug/bluetooth/hci0/adv_max_interval")
        return

