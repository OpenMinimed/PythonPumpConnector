import threading
import queue

from utils.log_manager import LogManager
from pysake.server import SakeServer
from pysake.constants import KEYDB_PUMP_EXTRACTED

from utils.singleton import Singleton

class SakeHandler(metaclass=Singleton):
    """
    Handle GATT setup for SAKE characteristic and its communication

    The SAKE characteristic has the sole purpose of passing handshake messages
    between the pump and us. The pump sends us messages by writing to our SAKE
    characteristic. We transmit messages by sending notifications for the same
    characteristic. This works by just setting the characteristic's value. The
    underlying GATT mechanism will then send the notification for us.

    This, of course, only makes sense if the pump has already subscribed to
    receiving these notifications. We use this action of subscribing to
    initialize the SAKE handshake.

    We also wire up the actual SAKE server that evaluates incoming messages
    and generates responses. The SAKE server is not at all involved in the
    GATT communication. It just operates on the message data. We, on the other
    hand, are not involved in processing the messages. We just handle their
    transport.
    """

    # whether the pump is already subscribed to our SAKE characteristic
    pump_subscribed: bool = False

    # the SAKE characteristic
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

        self.server = SakeServer(KEYDB_PUMP_EXTRACTED)
        return

    #region thread-safe APIs

    def notify_callback(self, is_notifying: bool, char):
        """
        GATT notification callback

        This gets called when the client subscribes to the SAKE characteristic
        or unsubscribes from it.
        """
        self._callback_queue.put(("notify", is_notifying, char))

    def write_callback(self, value: bytearray, options: dict):
        """
        GATT write callback

        This gets called when the client writes a message to the SAKE
        characteristic, i.e. when we receive a SAKE message.
        """
        self._callback_queue.put(("write", bytes(value), options))

    def _send(self, data: bytes):
        if self.char is None:
            raise RuntimeError("Sake char is none! You forgot to call set_char()!")
        self._sender_queue.put(data)
        return
    
    def is_done(self) -> bool:
        return self.server.get_stage() == 6

    #endregion

    #region actual logic

    def _handle_subscribe(self, is_notifying: bool, char):
        """Handle pump's request to start/stop receiving notifications from us"""

        self.logger.debug(f"got a sake notification start/stop request!")
        
        if self.char is None:
            self.logger.info(f"sake char is first seen as {char}")
            self.char = char

        if is_notifying and not self.pump_subscribed:
            self.logger.warning("pump wants to be friends with us!")
            self.pump_subscribed = True
            # Initiate the SAKE handshake by sending an all-zeros message.
            # This will trigger the SAKE client on the pump to send a message
            # back to us.
            zeroes = bytes(20)
            self._send(zeroes)

        if not is_notifying:
            self.pump_subscribed = False
            self.logger.error("pump disabled notifications!")

    def _handle_receive(self, value: bytes, options: dict):
        """Handle incoming SAKE messages"""

        value = bytes(value)
        self.logger.debug(f"sake write callback received: {value.hex()}")

        # If we have already completed the handshake, we do not expect any
        # more messages from the SAKE client. So just ignore them.
        if self.is_done():
            self.logger.warning(f"preventing sake-reset to get into handshake steps!")
            return

        # let SAKE server process the incoming message and generate a response 
        output = self.server.handshake(value)

        if output is None and self.is_done():
            self.logger.info("SAKE HANDSHAKE IS DONE!!! CONGRATULATIONS!")
        else:
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
                    # handle client's subscription/unsubscription
                    _, is_notifying, char = item
                    self._handle_subscribe(is_notifying, char)

                elif kind == "write":
                    # handle SAKE message received from client
                    _, value, options = item
                    self._handle_receive(value, options)

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
                self.logger.debug(f"sent data on sake port: {data.hex()}")
            except Exception as e:
                self.logger.exception(f"sake tx failed: {e}")

    #endregion

    # def close(self):
    #     self._stop_evt.set()
    #     self._sender_queue.put(b"")
    #     self._callback_queue.put(None)
