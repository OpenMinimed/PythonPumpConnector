# PythonPumpConnector

> [!WARNING]
> This is proof-of-concept code used mainly for reverse-engineering. Do not rely on it for therapy!


This script lets you connect to a 700-series Medtronic pump from a Linux computer, just like Medtronic's MiniMed Mobile app does, but without a mobile phone or any Medtronic software.

![screenshot](https://raw.githubusercontent.com/OpenMinimed/PythonPumpConnector/refs/heads/main/banner.png)

## Table of contents

1. [Table of contents](#table-of-contents)
2. [How to set this up](#how-to-set-this-up)
3. [How to use](#how-to-use)
   1. [Pairing](#pairing)
   2. [Reconnects](#reconnects)
   3. [Database viewer](#database-viewer)
4. [Debugging](#debugging)
5. [Advanced](#advanced)
   1. [Adjusting the advertising interval](#adjusting-the-advertising-interval)

## How to set this up

> [!IMPORTANT]
> Currently only Linux is supported.

1. Clone this repo, including submodules

    ```sh
    git clone --recurse-submodules git@github.com:OpenMinimed/PythonPumpConnector.git
    ```

2. Install system dependencies

    ```sh
    # Ubuntu/Debian (untested)
    sudo apt install libcairo2-dev pkg-config python3-dev python3-pip libgirepository1.0-dev libcairo-gobject2

    # Fedora (tested on 43)
    sudo dnf install cairo-devel pkg-config python3-devel gobject-introspection-devel cairo-gobject-devel
    ```

3. Install Python dependencies

    ```sh
    pip install -r requirements.txt
    ```

4. Get sources for BlueZ 5.66 (or older)

    Consult your distribution's guide or fetch the [upstream sources](https://github.com/bluez/bluez/tree/5.66).

5. Patch and rebuild BlueZ — force ATT_MTU to 23 bytes

    In `src/shared/gatt-server.c`, find `find_info_cb()` and the call to `encode_find_info_rsp()`. Insert `mtu = 23;` right before that call. Rebuild and reinstall BlueZ.

    **Why:** After the pump connects, BlueZ requests an MTU of 184 bytes (the pump's advertised max). The pump does not actually handle PDUs larger than 23 bytes — it stops responding, terminating the connection. The MiniMed Mobile app never sends larger PDUs even after an MTU exchange. Patching `find_info_cb()` is the only reliable fix (`ExchangeMTU = 23` in `main.conf` does not work).

    Tested and working on BlueZ 5.55 and 5.66, Linux 6.1.0-42-amd64.

6. Update BlueZ config

    In `/etc/bluetooth/main.conf`, section `[General]`, add `Privacy = device`. Restart:

    ```sh
    sudo systemctl restart bluetoothd
    ```

7. Patch bluezero (tested with v0.9.1 only)

    Find the bluezero install location (`pip show bluezero`). Open `bluezero/localGATT.py`, class `Characteristic`, function `WriteValue()`. Comment out the call to `self.Set()`:

    ```python
    def WriteValue(self, value, options):
        if self.write_callback:
            self.write_callback(dbus_tools.dbus_to_python(value),
                                dbus_tools.dbus_to_python(options))
        # REMOVED:
        # self.Set(constants.GATT_CHRC_IFACE, 'Value', value)
    ```

    **Why:** Without this patch, written characteristic data is echoed back instead of forwarding the response (see [bluezero#382](https://github.com/ukBaz/python-bluezero/issues/382)).

## How to use

The pump communicates over BLE, so you need a computer with Bluetooth LE support.

### Pairing

Pump and computer must be paired once. Once paired, reconnects do not require pairing again.

Open two terminals. In the first:

```bash
bluetoothctl --agent=NoInputNoOutput
```

`NoInputNoOutput` is essential — the pump requests the MITM flag but does not support LE Secure Connections, so the kernel falls back to *Just Works* pairing. Without this agent, pairing is rejected.

If your pump still shows another connected mobile device, remove it first (the pump only connects to one "phone" at a time).

On the pump, start searching for new devices. In the second terminal, run:

```bash
./main.py
```

The script advertises as `Mobile XXXXXX` (random number). After a few seconds, the pump should find it and prompt you to connect. Accept the pairing request in the `bluetoothctl` terminal when prompted.

Alternatively, you can provide a custom name instead of the random number (max. 7 characters):

```bash
./main.py <name>
```

After GATT discovery and the SAKE handshake, the script presents an interactive menu of commands for reading pump data (CGM, features, event history, etc.).

> [!NOTE]
> The script may prompt for `sudo` to set up BLE advertising.

### Reconnects

If the script was stopped after a successful SAKE handshake, reconnect without re-pairing:

```bash
./main.py --reconnect
```

The name used during pairing need not be supplied here again. The second terminal with `bluetoothctl` is not needed for reconnects.

### Database viewer

After syncing history data, explore the local SQLite database:

```bash
python3 -m database.viewer
```

This parses all stored records, prints them, lists event types, detects sequence-number gaps, and generates a daily datapoint-count graph (`history_graph.png`).

## Debugging

Capture BLE traffic for Wireshark analysis:

```bash
btmon -w $(date +"%Y-%m-%d_%T")_pump.log
```

Run this in a separate terminal before starting `main.py`.

Sometimes no BLE traffic is sent and pairing does not start — likely a GUI bug in the pump. Go back to `Paired Devices > Pair New Device` and retry. Disabling the BT adapter on the PC while the pump waits on a timeout regains button control faster.

## Advanced

### Adjusting the advertising interval

Most computers default to an advertising interval > 1 second. This works for initial pairing but can prevent reliable reconnects (the pump may miss sparse advertising packets while scanning intermittently to save battery).

To shorten the interval, use debugfs (requires `CONFIG_BT_DEBUGFS=y` in the kernel):

> [!NOTE]
> The script tries to automatically apply this workaround.


```sh
echo 50 > /sys/kernel/debug/bluetooth/hci0/adv_min_interval
echo 50 > /sys/kernel/debug/bluetooth/hci0/adv_max_interval
```

The actual interval is `value × 0.625 ms` (50 → ~31 ms). Change `adv_min_interval` first, then `adv_max_interval` (min must never exceed max).

If this fails with "operation not permitted", check kernel lockdown:

```sh
cat /sys/kernel/security/lockdown
```

If not `none`, disable Secure Boot in BIOS/EFI.

Verify with `btmon` — you should see:

```
Min advertising interval: 31.250 msec (0x0032)
Max advertising interval: 31.250 msec (0x0032)
```

This is only needed for reconnects. Initial pairing works fine with the default interval.