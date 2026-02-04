import threading
import queue

from log_manager import LogManager
from pysake.server import SakeServer
from pysake.constants import KEYDB_PUMP_EXTRACTED, KEYDB_PUMP_HARDCODED

class SakeHandler:

    pump_enabled: bool = False
    char = None

    def __init__(self):
        self.logger = LogManager.get_logger(self.__class__.__name__)

        self._sender_queue = queue.Queue()
        self._callback_queue = queue.Queue()
        self._stop_evt = threading.Event()

        self._tx_thread = threading.Thread(
            target=self._thread_sender,
            name="sake-sender",
            daemon=True,
        )
        self._tx_thread.start()

        self._cb_thread = threading.Thread(
            target=self._thread_callback,
            name="sake-callback",
            daemon=True,
        )
        self._cb_thread.start()

        self.server = SakeServer(KEYDB_PUMP_HARDCODED)
        #self.server = SakeServer(KEYDB_PUMP_EXTRACTED)
        return

    # region thread safe apis
    def notify_callback(self, is_notifying: bool, char):
        self._callback_queue.put(("notify", is_notifying, char))

    def write_callback(self, value: bytearray, options: dict):
        self._callback_queue.put(("write", bytes(value), options))

    def _send(self, data: bytes):
        if self.char is None:
            raise RuntimeError("Sake char is none! You forgot to call set_char()!")
        self.logger.debug(f"sake sending: {data.hex()}")
        self._sender_queue.put(data)
        return

    # region actual logic
    def _handle_notify(self, is_notifying: bool, char):
        if self.char is None:
            self.logger.info(f"sake char is first seen as {char}")
            self.char = char

        if is_notifying and not self.pump_enabled:
            self.logger.warning("pump wants to be friends with us!")
            self.pump_enabled = True
            zeroes = bytes(20)
            self._send(zeroes) # trigger sake client on the pump
            #self.server.handshake(zeroes) DONT feed it here!

        if not is_notifying:
            self.pump_enabled = False
            self.logger.error("pump disabled notifications!")

    def _handle_write(self, value: bytes, options: dict):
        value = bytes(value)
        # self.logger.info(
        #     f"sake write callback received: {value.hex()} "
        # )
        output = self.server.handshake(value)
        #self.logger.info(f"sake server response calculated: {output.hex()}")
        self._send(output)

    # region slave threads
    def _thread_callback(self):
        while not self._stop_evt.is_set():
            try:
                item = self._callback_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                kind = item[0]

                if kind == "notify":
                    _, is_notifying, char = item
                    self.logger.debug("got a sake notification!")
                    self._handle_notify(is_notifying, char)

                elif kind == "write":
                    _, value, options = item
                    self.logger.debug("got a sake write!")
                    self._handle_write(value, options)

                else:
                    raise RuntimeError(f"Unknown callback type: {kind}")

            except Exception as e:
                self.logger.exception(f"Callback processing failed: {e}")

    def _thread_sender(self):
        """
        The ONLY place where real char.set_value() is allowed.
        """
        while not self._stop_evt.is_set():
            try:
                data = self._sender_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.char.set_value(list(data))
                #self.logger.info(f"sent data on sake port: {data.hex()}")
            except Exception as e:
                self.logger.exception(f"sake tx failed: {e}")

    # def close(self):
    #     self._stop_evt.set()
    #     self._sender_queue.put(b"")
    #     self._callback_queue.put(None)
