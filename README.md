# PythonPumpConnector

> [!WARNING]  
> Read this carefully since there are a lot of gotchas and things that can go wrong!

You can advertise, connect, perform the handshake and talk with a pump using this script.

Currently only Linux is supported.


![screenshot](https://raw.githubusercontent.com/OpenMinimed/PythonPumpConnector/refs/heads/main/banner.png)

## Table of contents

- [Table of contents](#table-of-contents)
- [How to use](#how-to-use)
- [Prerequisites](#prerequisites)
- [Fixing ATT\_MTU size](#fixing-att_mtu-size)
- [Fixing the Bluezero echo problem](#fixing-the-bluezero-echo-problem)
- [IO capability](#io-capability)
- [Pairing confirmation](#pairing-confirmation)
- [Adjusting the advertising interval](#adjusting-the-advertising-interval)
- [Random failures](#random-failures)
- [Debugging](#debugging)

## How to use

The goal is to connect to a 700-series Medtronic pump from our own computer, just like Medtronic's MiniMed Mobile app does, but with no mobile phone and no Medtronic software involved. The connection is over Bluetooth LE, so you will need a computer that supports it.

If your pump still lists a phone as connected device you have to remove that first because the pump can only connect to one "phone" at a time. On your pump, start the search for new devices to connect to. Then run `main.py` from this repository in a terminal. The script will choose a device name like "Mobile 123456" with a random number (i.e. it changes every time you run the script). It includes this name in its log output for reference and uses it to advertise as suitable Bluetooth LE device for the pump to connect to. Note that the script may ask you to input your password because the steps necessary to configure and run Bluetooth LE advertising typically need to be executed as superuser (using `sudo`).

After a couple of seconds, the pump should have found the device and prompt you to connect to it. Confirming to connect should trigger a pairing request on your computer which you need to accept (see corresponding section below).

Pump and script then spend another couple of seconds in GATT discovery after which the script finally initiates the SAKE handshake. See the script's log output in the terminal for details. Any problems during that process are also reported there.

The script will currently simply restart the advertising after any problems in that process. You can stop it by pressing `Ctrl+C` in the terminal.

If you stop the script after a successful SAKE handshake (thus terminating the BLE connection) and later want to reconnect to the pump without going through the whole pairing procedure again, you can call `main.py` with the  `-p` argument and pass it the random number that was used in the previous pairing step. Your pump should still show it as part of the device name it is currently connected to. This will handle the reconnect from the pump and also start another SAKE handshake.


## Prerequisites

* Clone this repo with submodules
	```sh
	git clone --recurse-submodules git@github.com:OpenMinimed/PythonPumpConnector.git
	```
* Install system dependencies
	```sh
	# Ubuntu/Debian (untested)
	sudo apt install libcairo2-dev pkg-config python3-dev libgirepository1.0-dev libcairo-gobject2

	# Fedora (tested on 43)
	sudo dnf install cairo-devel pkg-config python3-devel gobject-introspection-devel cairo-gobject-devel
	```
* Install Python dependencies
	```sh
	pip install -r requirements.txt
	```

## Fixing ATT_MTU size

After the pump connecting to our script, BlueZ seems to routinely send a request to increase the maximum allowed MTU size (`ATT_EXCHANGE_MTU_REQ`). The default MTU size is 23 bytes. The pump answers this request with a `ATT_EXCHANGE_MTU_RSP` indicating that it supports an MTU size of at most 184 bytes.

The problem is that the pump does not actually seem to support that size. If BlueZ sends PDUs > 23 bytes during the following GATT discovery, the pump just stops responding, terminating the connection.

The MiniMed Mobile app on Android never seems to send that request. Interestingly, it does on iOS. But neither of them are then actually sending larger than default PDUs.


On Android, we found out that even though the same 184 is exchanged, the app never performs <code>requestMtu()</code> and the data rate seems to stay on the default 23 bytes (at least on the observed device models).

So, the current workaround is to force the smaller MTU size on BlueZ by patching its sources: In <code>src/shared/gatt-server.c</code>, function <code>find_info_cb()</code> passes the MTU size to <code>encode_find_info_rsp()</code> which builds the response packet. Just before that call you can hardcode <code>mtu = 23;</code> and after recompilation it should work.

Please consult your distrubtion's guide or the internet on how to re-build system packages.

Note that this only fixes the one specific scenario in which we observed BlueZ sending larger PDUs: responses to the pump's `ATT_FIND_INFORMATION_REQ`.

Also note that <code>ExchangeMTU = 23</code> in <code>/etc/bluetooth/main.conf</code> does not seem to work (at least for me).

Tested and working versions:

- Linux 6.1.0-42-amd64
- Bluez 5.55 and 5.66


## Fixing the Bluezero echo problem

There is an echo bug (or feature?) in the Bluezero library, which causes the written data to be sent back on a characteristic. This is exactly the inverse of what we actually need, since we want to answer with the next handshake data instead. The fix is fairly simple and is highlighted in the [Bluezero #382 issue](https://github.com/ukBaz/python-bluezero/issues/382). You basically need to comment out the line <code>self.Set(constants.GATT_CHRC_IFACE, 'Value', value)</code> in the <code>WriteValue</code> function in <code>localGATT.py</code>. This was confirmed to be working on bluezero v0.9.1.


## IO capability

Setting IO capability to 3 (<code>NoInputNoOutput</code>) is also very important, because the device asks for the MITM flag, but does not support LE Secure Connections. This makes the kernel default to the *Just Works* method and will not immediately reject the pairing request. This is performed automatically by the script.


## Pairing confirmation

By default, you will need to have a desktop client that handles the acceptance of pairing requests. Be ready for desktop notifications and quickly pressing accept on them!

If there is no client running, the kernel automatically rejects the pairing requests. One way we got this to work on the command line was by running `bluetoothctl --agent=NoInputNoOutput` in a separate terminal before starting `main.py`. `bluetoothctl` will then prompt for accepting/declining the pairing request in the terminal.


## Adjusting the advertising interval

With BlueZ, most computers seem to be using a rather long default advertising interval of > 1 second, i.e. successive advertising packets are sent every second (or even less frequent). This does not seem to be a problem for the initial pairing step where the pump is instructed to look for advertising packets from a suitable device. Scanning for such a devices frequently is rather energy-heavy, but it makes sure the device is found quickly.

If both communication partners are later disconnected (devices are too far apart, Bluetooth is temporarily disabled etc.), the pump tries to reconnect. But since it does not know if the other side is gone for long, it does not make sense for the pump to spend lots of its battery power on scanning for the partner in short intervals. If our advertising packets are sent only every second or so, chances are high that the pump will miss them if it only scans for them every couple of seconds, too.

Please note that we do not know if the pump actually behaves that way (it is not trivial to measure when and how often the pump is actually scanning), but it would make sense for a battery-powered device. Also, we could not get reconnects to work with long advertising intervals. However, reconnects work reliably when using a short advertising interval.

Setting a shorter advertising interval seems to be more complicated than it needs to be. So far, the only way we could get this to work was through debugfs. This requires, first of all, a kernel built with `CONFIG_BT_DEBUGFS=y`. Check your kernel config (typically in `/boot/config-$(uname -r)` to see if this option is set. Then set the advertising interval by writing the following two values:

```sh
echo 50 > /sys/kernel/debug/bluetooth/hci0/adv_min_interval
echo 50 > /sys/kernel/debug/bluetooth/hci0/adv_max_interval
```

Assuming that their inital value is something large (like 2048), make sure to first change the _min_ value, then the _max_ value, just as above. The write operation will throw an error otherwise because _min_ must apparently never be greater than _max_.

Note that writing these values might not work and you get _operation failed_ or something like that in response. If that is the case, check if kernel lockdown is enabled:

```sh
echo /sys/kernel/security/lockdown
```

If anything else than `none` is selected, you probably need to disable Secure Boot in your BIOS/EFI settings.

The actual advertising interval is computed by multiplying the value in `adv_min_interval` or `adv_max_interval` by 0.625 ms. You can check the output of `btmon` to verify the correct interval is used. It will look something like this if `main.py` starts the advertising:

```
@ MGMT Command: Add Advertising (0x003e) plen 40                       {0x0002} [hci0] 5.832981
        Instance: 1
        Flags: 0x00000000
        Duration: 5
        Timeout: 5
        Advertising data length: 29
        Flags: 0x06
          LE General Discoverable Mode
          BR/EDR Not Supported
        Company: Medtronic Inc. (505)
          Data: 004d6f62696c652039343330393300
        TX power: 1 dBm
        16-bit Service UUIDs (complete): 1 entry
          Medtronic Inc. (0xfe82)
        Scan response length: 0
@ MGMT Event: Advertising Added (0x0023) plen 1                        {0x0001} [hci0] 5.832987
        Instance: 1
< HCI Command: LE Set Advertising Parameters (0x08|0x0006) plen 15           #3 [hci0] 5.833017
        Min advertising interval: 31.250 msec (0x0032)
        Max advertising interval: 31.250 msec (0x0032)
        Type: Connectable undirected - ADV_IND (0x00)
        Own address type: Public (0x00)
        Direct address type: Public (0x00)
        Direct address: 00:00:00:00:00:00 (OUI 00-00-00)
        Channel map: 37, 38, 39 (0x07)
        Filter policy: Allow Scan Request from Any, Allow Connect Request from Any (0x00)
```

Note that this adjustment is only necessary for _reconnects_. The initial connection and pairing seems to work just fine with the long default advertising intervals. So if you have trouble changing the interval on your machine and only want to the get the initial connection to the pump going, do not (yet) waste your time with this adjustment.


## Random failures

Sometimes no BT traffic actually gets sent to the PC and the pairing does not even start. We believe this is a GUI bug in the pump code. The workaround is very simple, just go back to the <code>Paired Devices > Pair New Device</code> menu and retry. If you disable the BT adapter on your PC while the pump is waiting on a timeout, you can regain control of your pump's buttons faster.


## Debugging

Use <code>btmon</code>. You can also save a btsnoop file using the flag <code>-w</code>, that you can load with Wireshark later.
