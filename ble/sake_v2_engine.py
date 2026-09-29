"""
Adapts PythonSake's tools/sake_v260_emulate/engine.py -- which runs the
real, unmodified Medtronic libandroid-sake-lib.so (v260) protocol-v2
(passkey/SRP-6a) SAKE server inside an ARM emulator -- to the same
.handshake(value)/.is_done() interface pysake.server.SakeServer (v1)
exposes, so SakeHandler can drive either protocol version identically.

This is the real thing, not a reimplementation: every crypto operation is
whatever the real library computes. See PythonSake's
tools/sake_v260_emulate/README.md for how the protocol was reverse
engineered (three separate cases where Ghidra's decompile actively misread
this library, only resolved by running the real code or reading raw
disassembly).

Permit key material status: the exchange needs FOUR 16-byte secrets --
two pairs, "server's own" (decrypt+mac) and "client's own" (decrypt+mac) --
and BOTH sides need to know all four (each side decrypts/verifies incoming
messages with its own pair, and must also know the peer's pair to correctly
construct outgoing messages addressed to that peer; see PythonSake's README,
"Solving the permit exchange"). We're the SAKE-protocol-server (see
CONNECTOR_DEVICE_TYPE below), so:

- our_decrypt_key / our_mac_key = the "server's own" pair. These ARE real:
  pysake.constants.KEYDB_PUMP_EXTRACTED (already extracted from and proven
  against a real pump for protocol v1) stores exactly these two 16-byte
  values, in its StaticKeys.permit_decrypt_key / .permit_auth_key fields --
  v1 never reads them (it only uses derivation_key/handshake_auth_key/
  handshake_payload), but they were captured in the same extraction and are
  the correct real values for v2's permit step too (confirmed structurally:
  PythonSake's pysake/keys.py already named these fields identically to
  what this session's independent RE of the v2 permit path found, byte
  offset for byte offset, before any v2 work started).
- peer_decrypt_key / peer_mac_key = the "client's (pump's) own" pair. NOT
  present in KEYDB_PUMP_EXTRACTED -- that database only ever needed to
  carry our half for v1's symmetric-secret scheme. These remain placeholder
  values below. Sourcing them is a separate RE task, most likely via the
  IDD Secure Control Point (0x0109) / PublicKeyExchangeApiImpl flow this
  project's Documentation repo describes.

Without real peer_* values, this completes a handshake with anything
running the same engine (see PythonSake's selftest_full_handshake.py) but
will NOT pair with a real pump -- it fails the permit's self-consistency
checksum, the same err=18/PERMIT_RECEIVED_INVALID this session's harness
work debugged at length.
"""
from dataclasses import dataclass
import logging
import os
import sys

from utils.log_manager import LogManager


def _sake_v2_engine_module():
    """
    Import PythonSake's tools/sake_v260_emulate/engine module. Done lazily
    (not at file import time) since it pulls in unicorn/capstone/pyelftools
    and maps+emulates an ARM .so on first import -- no reason to pay that
    cost unless --sake-v2 is actually used.
    """
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "PythonSake",
                      "tools", "sake_v260_emulate")
    d = os.path.abspath(d)
    if not os.path.isdir(d):
        raise FileNotFoundError(f"missing PythonSake submodule checkout at {d}")
    if d not in sys.path:
        sys.path.append(d)
    import engine  # noqa: PLC0415 -- intentionally lazy, see docstring
    return engine


# Device types per pysake.device_types.DeviceType / the real SAKE_DEVICE_TYPE_E.
PUMP_DEVICE_TYPE = 1        # InsulinPump -- plays the SAKE_CLIENT role
CONNECTOR_DEVICE_TYPE = 4   # MobileApplication -- we play the SAKE_SERVER role,
                            # matching this codebase's v1 SakeHandler already
                            # running pysake.server.SakeServer (also SERVER).


def _real_server_pair():
    """
    our_decrypt_key/our_mac_key sourced from the real, pump-extracted
    pysake.constants.KEYDB_PUMP_EXTRACTED -- see the module docstring above
    for why these two (and only these two) fields are real.
    """
    from pysake.constants import KEYDB_PUMP_EXTRACTED
    sk = KEYDB_PUMP_EXTRACTED.remote_devices[PUMP_DEVICE_TYPE]
    return sk.permit_decrypt_key, sk.permit_auth_key


@dataclass
class PermitKeys:
    """
    The four 16-byte identity secrets the permit exchange needs (see the
    module docstring above). our_decrypt_key/our_mac_key default to the
    real values from KEYDB_PUMP_EXTRACTED. peer_decrypt_key/peer_mac_key
    are still placeholders -- that secret isn't in KEYDB_PUMP_EXTRACTED and
    hasn't been sourced elsewhere yet. A handshake built with placeholder
    peer_* values will only ever complete against another instance using
    the *same* placeholder values (e.g. PythonSake's own selftest), never a
    real pump.
    """
    our_decrypt_key: bytes = None
    our_mac_key: bytes = None
    peer_decrypt_key: bytes = bytes(range(0xA0, 0xB0))
    peer_mac_key: bytes = bytes(range(0xC0, 0xD0))

    def __post_init__(self):
        if self.our_decrypt_key is None or self.our_mac_key is None:
            real_decrypt, real_mac = _real_server_pair()
            self.our_decrypt_key = self.our_decrypt_key or real_decrypt
            self.our_mac_key = self.our_mac_key or real_mac
        for f in (self.our_decrypt_key, self.our_mac_key, self.peer_decrypt_key, self.peer_mac_key):
            assert len(f) == 16


class SakeV2EngineAdapter:
    def __init__(self, passkey: int, permit_keys: PermitKeys = None):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        if permit_keys is None:
            self.logger.warning(
                "SakeV2EngineAdapter: no --sake-v2-permit-keys supplied -- "
                "defaulting to our_decrypt_key/our_mac_key from the real "
                "KEYDB_PUMP_EXTRACTED, but peer_decrypt_key/peer_mac_key are "
                "still placeholders. This will NOT pair with a real pump "
                "(the permit's self-consistency checksum will fail). See "
                "ble/sake_v2_engine.py's module docstring."
            )
            permit_keys = PermitKeys()

        engine = _sake_v2_engine_module()
        self._engine = engine

        our_permit = engine.build_permit_plaintext(CONNECTOR_DEVICE_TYPE, permit_keys.peer_mac_key)
        our_material = engine.build_permit_key_material(
            permit_keys.our_decrypt_key,
            permit_keys.our_mac_key,
            engine.aes_ecb_encrypt(our_permit, permit_keys.peer_decrypt_key),
        )
        keydb = engine.build_key_database(CONNECTOR_DEVICE_TYPE, PUMP_DEVICE_TYPE, our_material)
        self._server = engine.SakeV2Server(passkey, keydb)
        self._initial_message = None

    def initial_message(self) -> bytes:
        """
        The message to send to the pump to kick off the handshake -- v2's
        equivalent of v1's hardcoded bytes(20) "kick" in
        SakeHandler._handle_subscribe.
        """
        if self._initial_message is None:
            self._initial_message = self._server.step(None)
        return self._initial_message

    def handshake(self, input_data: bytes) -> bytes | None:
        try:
            return self._server.step(input_data)
        except self._engine.SakeHandshakeFailed as e:
            self.logger.error(f"protocol-v2 handshake failed: {e}")
            return None

    def is_done(self) -> bool:
        return self._server.is_done

    def encrypt(self, data: bytes) -> bytes:
        return self._server.secure_for_sending(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._server.unsecure_after_receiving(data)
