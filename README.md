#############################
# 802.15.4 monitor          #
# based on Texas Instrument #
# CC2531 USB dongle         #
#############################

This monitor is composed of multiple files: 
CC2531.py, receiver.py, interpreter.py, gps.py, sniffer.py, decoder.py

It requires the following extra packages:
libusb-1: http://www.libusb.org/wiki/libusb-1.0
python-libusb1: https://github.com/vpelletier/python-libusb1
pySerial (for gps.py): http://pyserial.sourceforge.net/
And the libmich library from https://github.com/mitshell/libmich

Install it by running:
*sudo python setup.py install*
or just run it from your home directory (ensure it's in your python path).
Warning: to get control over your USB device(s) in Linux / UNIX,
you need to manage your system rights properly
(e.g. run it as root -however it's insecure to run such an unknown 
program as root...-, or with a login in the root group, or with the proper 
udev rules, ...)

run it by calling sniffer.py:
./python sniffer.py --help


# Files' description and use

## CC2531.py
This is the *driver* for a CC2531 USB dongle. 
It is making use of libusb-1 and its python wrapper python-libusb1.
The class CC2531 handles the main controls (init, set channel...)
and 802.15.4 frame reading methods.

## receiver.py
This is the main handler for a CC2531 USB dongle.
It initializes the communication with the dongle with a CC2531 instance,
and then listens to a single channel, or multiple channels alternatively.
Channels' list is defined in `CHAN_LIST` class attribute.
Hopping period (for multi-channels) is defined in `CHAN_PERIOD` class attribute.
Due to the time needed by the dongle to re-tune itself (~500ms), 
do not expect to do quick channel hopping. 

802.15.4 frames received are then forwarded to a server with some metadata:
the channel number, the epoch time and (if available) the GPS position.
The `GPS` class attribute allows a receiver instance to possibly
request a GPS reader running in background (this is handled by gps.py).
The `SOCK_ADDR` class attribute defines the server address
to forward captured frames to. If a network address is provided, 
an UDP socket is used, if a filename is given, a UNIX file socket is used.

The exact structure of a packet forwarded is given below:
    The structure is a set of TLV fields:
    Tag : uint8, Length : uint8, Value : char*[L]
    Tag=0x01, 802.15.4 channel, uint8
    Tag=0x02, epoch time at frame reception, ascii encoded
    Tag=0x03, position at frame reception (if GPS is available)
    Tag=0x10, 802.15.4 frame within TI PSD structure (default for CC2531)
    Tag=0x20, 802.15.4 frame

## interpreter.py
This is the server which receives all packets containing 802.15.4 frames
captured by receiver(s). It also interprets it (print it on stdout and/or 
a temporary file), in case the FCS of the 802.15.4 frame received is correct.

## gps.py
This is a service requesting a GPS available over a serial port (/dev/ttyUSBx).
It gets information within NMEA format,
and lets receivers store and use the GPMRC information when forwarding a
802.15.4 frame.

## sniffer.py
This is the python executable file.
Call it with --help to see available options.

## decoder.py
This is a little python executable file.
Call it to print interpretation of a pcap file that is a capture 
of IEEE 802.15.4 frames forwarded over UDP by receivers' instances.
