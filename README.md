# PythonPumpConnector

> [!WARNING]  
> Read this carefully since there are a lot of gotchas and things that can go wrong!

You can advertise, connect, perform the handshake and talk with a pump using this script.

Currently only Linux is supported.

![screenshot](https://raw.githubusercontent.com/OpenMinimed/PythonPumpConnector/refs/heads/main/banner.png)


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


## IO capability

Setting IO capability to 3 (<code>NoInputNoOutput</code>) is also very important, because the device asks for the MITM flag, but does not support LE Secure Connections. This makes the kernel default to the Just Works method and will not immediately reject the pairing request. This is performed automatically by the script.


## Desktop confirmation

By default, you will need to have a desktop client that handles the acceptance of pairing requests. If you are running in a headless mode, then the kernel automatically rejects the pairing requests. I am sure that there is a way to accept it from the CLI, but I have not checked it. Be ready for desktop notifications and quickly pressing accept on them!

## Random failures

Sometimes no BT traffic actually gets sent to the PC and we believe this is a GUI bug in the pump code. The workaround is very simple, just go back to the <code>Paired Devices > Pair New Device</code> menu and retry.


## Debugging

Use <code>btmon</code>. You can save a btsnoop file using the flag <code>-w</code>, that you can load with Wireshark later.