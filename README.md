# PythonPumpConnector

You can advertise, connect, perform the handshake and talk with a pump using this script.

> [!WARNING]  
> Bluez needs to be patched for it to work!

## MTU problem

The pump asks for an MTU of 184 bytes, however we have had trouble if Bluez automatically exchanged to this number.

On Android, we found out that even though the same 184 is exchanged, the app never performs <code>requestMtu()</code> and the data rate seems to stay on the default 23 bytes (at least on the observed device models).

So, the current workaround is to force Bluez by patching it: in <code>src/shared/gatt_server.c</code> function <code>find_info_cb()</code> passes the MTU size <code>encode_find_info_rsp()</code>, which builds the response packet. Just before that call you can hardcode <code>mtu = 23;</code> and after recompilation it should work.

Please consult your distrubtion's guide or the internet on how to re-build system packages.

## IO capability

Setting IO capability to 3 (NoInputNoOutput) is also very important, because the device asks for the MITM flag, but does not support LE Secure Connections. This makes the kernel default to the Just Works method and will not immediately reject the pairing request. 