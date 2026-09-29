import threading
import queue

from utils.log_manager import LogManager
from pysake.server import SakeServer as SakeV1Server
from pysake.constants import KEYDB_PUMP_EXTRACTED
# pysake.v2's generic-SRP-library approach is retired -- see the module
# docstring at the top of pysake/v2.py. --sake-v2 now runs
# ble.sake_v2_engine.SakeV2EngineAdapter instead, which drives the real
# Medtronic libandroid-sake-lib.so (v260) via PythonSake's
# tools/sake_v260_emulate -- see that module's docstring and README for
# status (handshake + secure messaging both proven working; real per-pump
# permit key material still needed to actually pair with a pump).
from ble.sake_v2_engine import SakeV2EngineAdapter, PermitKeys

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

    def __init__(self, use_sake_v2: bool = False, v2_passkey: int | None = None,
                 v2_permit_keys: PermitKeys | None = None):
        """
        use_sake_v2: run the protocol-v2 (passkey/SRP-6a) server instead of
        the v1 challenge/CMAC one, via ble.sake_v2_engine.SakeV2EngineAdapter
        (the real libandroid-sake-lib.so v260, emulated). Defaults to the v1
        server, which is what pairs with a real pump today -- v2 still needs
        real per-pump permit key material to do the same; see
        ble/sake_v2_engine.py.
        """
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.use_sake_v2 = use_sake_v2
        self._v2_permit_keys = v2_permit_keys

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

        if use_sake_v2:
            self.logger.warning(
                "running the protocol-v2 (passkey/SRP-6a) SAKE server via "
                "the real libandroid-sake-lib.so engine -- see "
                "ble/sake_v2_engine.py for current status"
            )
            self.server = SakeV2EngineAdapter(v2_passkey, permit_keys=v2_permit_keys)
        else:
            self.server = SakeV1Server(KEYDB_PUMP_EXTRACTED)
        return

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt a post-handshake payload to send to the pump."""
        if self.use_sake_v2:
            return self.server.encrypt(data)
        return self.server.session.server_crypt.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt a post-handshake payload received from the pump."""
        if self.use_sake_v2:
            return self.server.decrypt(data)
        return self.server.session.server_crypt.decrypt(data)

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
            raise RuntimeError("SAKE characteristic not set")
        self._sender_queue.put(data)
        return
    
    def is_done(self) -> bool:
        return self.server.is_done()

    #endregion

    #region actual logic

    def _handle_subscribe(self, is_notifying: bool, char):
        """Handle pump's request to start/stop receiving notifications from us"""

        self.logger.debug(f"Receiving SAKE notification start/stop request")

        if self.char is None:
            self.logger.info(f"Setting SAKE characteristic: {char}")
            self.char = char

        if is_notifying and not self.pump_subscribed:
            self.logger.warning("pump wants to be friends with us!")
            self.pump_subscribed = True
            # Initiate the SAKE handshake. v1's first server->client message
            # happens to always be 20 zero bytes; v2's depends on the engine
            # state (passkey, key database), so ask it directly instead of
            # assuming the same hardcoded bytes.
            self.logger.info("Initiating SAKE handshake")
            if self.use_sake_v2:
                kickoff = self.server.initial_message()
            else:
                kickoff = bytes(20)
            self._send(kickoff)

        if not is_notifying:
            self.pump_subscribed = False
            self.logger.error("pump disabled notifications!")

    def _handle_receive(self, value: bytes, options: dict):
        """Handle incoming SAKE messages"""

        value = bytes(value)
        self.logger.debug(f"RX: {value.hex()}")

        # If we have already completed the handshake, we do not expect any
        # more messages from the SAKE client. So just ignore them.
        if self.is_done():
            self.logger.warning(f"Handshake already completed. Ignoring unexpected message.")
            return

        # let SAKE server process the incoming message and generate a response 
        output = self.server.handshake(value)

        if output is not None:
            self._send(output)

        if self.is_done():
            self.logger.info("SAKE HANDSHAKE IS DONE!!! CONGRATULATIONS!")

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
                self.logger.debug(f"TX: {data.hex()}")
                self.char.set_value(list(data))
            except Exception as e:
                self.logger.exception(f"Sending SAKE message failed: {e}")

    #endregion

    # def close(self):
    #     self._stop_evt.set()
    #     self._sender_queue.put(b"")
    #     self._callback_queue.put(None)
