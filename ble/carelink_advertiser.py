from ble.advertiser import Advertiser
from utils.log_manager import LogManager


class CareLinkAdvertiser(Advertiser):
    adapter_addr: str
    confirmation_code: int

    def __init__(self, adv_name: str, adapter_addr: str, confirmation_code: int):
        """
        adv_name:          name for advertising
        adapter_addr:      MAC address of Bluetooth adapter in use
        confirmation_code: 6-digit pump confirmation code
        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.confirmation_code = confirmation_code

        # convert adapter's MAC address from string to bytes
        tok = adapter_addr.split(":")
        if len(tok) != 6:
            raise Exception(f"Malformed adapter MAC address: {adapter_addr}")
        try:
            self.adapter_addr = bytes.fromhex("".join(tok))
        except ValueError:
            raise Exception(f"Malformed adapter MAC address: {adapter_addr}")

        # the pump only accepts advertisers with a specific naming scheme
        if not self.__is_valid_adv_name(adv_name):
            raise Exception(f"Invalid advertising name given: {adv_name}")

        super().__init__(adv_name)

    def _create_adv_cmd(self) -> str:
        data = ""

        # Flags: we have turned BR/EDR off in self.startup_commands
        data += "02 01 06"

        # 16-bit Service Class UUIDs (incomplete): SAKE
        data += "03 02 82 fe"

        # Device Name
        length = 1 + len(self.adv_name)
        data += f"{length:02x} 09 {self.adv_name.encode().hex()}"

        # connection as CareLink device requires advertising with a special
        # hash in the scan response data
        adv_hash = self.__advertisement_hash(self.adapter_addr, self.confirmation_code)
        scan_rsp_data = f"0c ff {adv_hash.hex()}".replace(" ", "")

        self.logger.debug(f"Pump confirmation code: {self.confirmation_code:06}")
        self.logger.debug(f"Adapter MAC address: {self.adapter_addr.hex()}")
        self.logger.debug(f"Advertisement hash: {adv_hash.hex()}")

        data = data.replace(" ", "")

        # timeout is how long the bluez object lives (??)
        # set duration and timeout to the same for now, idk

        full_cmd = f"sudo btmgmt add-adv -d {data} -s {scan_rsp_data} -t {self.fake_adv_time} -D {self.fake_adv_time} {self.instance_id}"
        return full_cmd

    @staticmethod
    def __advertisement_hash(mac: bytes, code: int):
        def fnv1(data: bytes):
            """
            FNV-1 hash

            https://en.wikipedia.org/wiki/Fowler%E2%80%93Noll%E2%80%93Vo_hash_function
            """

            FNV_BASE  = 0xcbf29ce484222325
            FNV_PRIME = 0x100000001b3
            FNV_SIZE  = 2**64

            h = FNV_BASE

            for byte in data:
                h = (h * FNV_PRIME) % FNV_SIZE
                h = h ^ byte

            return h

        assert len(mac) == 6
        assert code <= 999999

        # Concat MAC and confirmation code into a 64-bit integer. This drops the
        # MAC's uppermost nibble!
        #
        # MAC bytes:  aA bB cC dD eE fF  (6 bytes          -> 48 bits)
        # code bytes: _G hH iI           (6 integer digits -> 20 bits)
        #
        # -> Ab Bc Cd De Ef FG hH iI
        n = (int.from_bytes(mac, "big") & 0x00000fff_ffffffff) << 20
        n += code
        message = n.to_bytes(length=8, byteorder="big")

        # reverse the byte array
        message = message[::-1]

        # compute the actual hash
        h = fnv1(message).to_bytes(length=8, byteorder="big")

        # reverse the byte array
        h = h[::-1]

        # NOTE: We could easily skip the explicit reversing of byte arrays by just
        #       specifying byteorder "little" in the previous steps. Let's keep it
        #       explicit to more clearly see what is going on.

        # add fixed prefix to form the final advertisement hash
        return bytes([0xf9, 0x01, 0x01]) + h

    @staticmethod
    def __is_valid_adv_name(s: str) -> bool:
        # TODO: check max length of advertising name
        return s.startswith("PC")

