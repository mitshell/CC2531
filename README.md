==================================
# 802.15.4 monitor
==================================

## Usage

This monitor works with Texas Instruments CC2531 USB dongles and their default 
firmware (no need to reflash them).

It drives them thanks to libusb, collects USB frames and enriches them with
channel number, timestamp, and position (in case a GPS is available over a 
serial port).
Multiple dongles can be driven, all of them send their collected information
over UDP (or a file socket) to a server which decodes IEEE802154 MAC frames
and nicely print them on screen (and within a file, if needed).

It requires the following extra packages:
* libusb-1: http://www.libusb.org/wiki/libusb-1.0
* python-libusb1: https://github.com/vpelletier/python-libusb1
* pySerial (for gps.py): http://pyserial.sourceforge.net/
* and the libmich library: https://github.com/mitshell/libmich

Install it by running *sudo python setup.py install*, or just run it from your 
home directory (ensure it's in your PYTHONPATH).

Warning: to get control over your USB device(s) in Linux / UNIX, you need to 
manage your system rights properly (e.g. run it as root, however it's insecure 
to run such an unknown program as root..., or with a login in the root group, 
or with the proper udev rules, ... just find your ways).

Simply run it by calling sniffer.py *python ./sniffer.py --help*.

## OS

This program is known to work on Linux, and known to not work on Windows. It 
seems that the winusb backend used by libusb-1 does not support certain USB
controls required by the dongles.

So for Windows user, just use Texas Instruments Packet Sniffer software.


## Software description

The software is structured as followed:

* CC2531.py is the USB *driver* for a single CC2531 dongle.

   The class CC2531 handles the main USB controls (init, set channel...) and 
   802.15.4 frames' reading methods.

* gps.py is a little class to collect GPS information over a serial port.

* receiver.py is the main handler for a CC2531 USB dongle.

   It initializes the communication with the dongle by instantiating a CC2531 
   class, and then listens to a single channel, or multiple channels
   alternatively. Channels' list is defined in `CHAN_LIST` class attribute. 
   Hopping period (for multi-channels) is defined in `CHAN_PERIOD` class
   attribute. Due to the time needed by the dongle to re-tune itself (~500ms), 
   do not expect to do quick channel hopping. When a 802.15.4 frame is read,
   metadata are added (channel number, timestamp, GPS position) and everything
   is packed and sent over a socket defined in `SOCK_ADDR` to the interpreter.

* interpreter.py is the main server which collects and interprets information
coming from all CC dongles.
   
   It collects receivers' packet over the socket, and interpret them with the
   IEEE802154 decoder from libmich. It can also record all those textual info
   into a file in /tmp.

* sniffer.py is the main executable.
   
   It creates an interpreter (/ server) and drives as many CC dongles as listed 
   on USB ports of the computer.

* decoder.py is an independent little python executable file.

   You can call it to print interpreted data of a pcap file that is a capture 
   of IEEE 802.15.4 frames forwarded over UDP by receivers' instances.

## Packing structure

The exact structure used between receivers' instances and the interpreter, to 
pack information is described below:

The structure is a set of TLV fields:
Tag : uint8, Length : uint16 (BE), Value : char*[Length].
* Tag=0x01, 802.15.4 channel, uint8
* Tag=0x02, epoch time at frame reception (ascii)
* Tag=0x03, position at frame reception (if GPS is available)
* Tag=0x10, 802.15.4 frame within TI USB structure (default for CC2531)
* Tag=0x20, 802.15.4 raw MAC frame

The whole structure is prefixed with a global length encoded as an uint32 (BE).
