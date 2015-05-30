# -*- coding: UTF-8 -*-
#/**
# * Software name: CC2531
# * Version: 0.1.0
# * Library to drive TI CC2531 802.15.4 dongle to monitor channels
# * Copyright (C) 2013 Benoit Michau, ANSSI.
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the CeCILL-B license as published here:
# * http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# *
# *--------------------------------------------------------
# * File Name : CC2531.py
# * Created : 2013-11-13
# * Authors : Benoit Michau, ANSSI
# *--------------------------------------------------------
# */
#!/usr/bin/python2
#
###
# 802.15.4 sniffer based on Texas Instruments CC2531 USB dongle
#
# uses libusb1
# http://www.libusb.org/
# and python-libusb1
# https://github.com/vpelletier/python-libusb1/
###

from binascii import hexlify, unhexlify
from time import sleep
import platform
try:
    import usb1
    import libusb1
except:
    print('ERROR: cannot import python libusb1 wrapper.')
    exit()

# export filtering
__all__ = ['VID', 'PID', 'CHANNELS', 'get_CC2531', 'CC2531', 'test']

# CC2531 USB identifiers
VID = 0x0451
PID = 0x16ae
#
# IEEE 802.15.4 2.4GHz ISM band channels
CHANNELS = {
    0x0B : 2405,
    0x0C : 2410,
    0x0D : 2415,
    0x0E : 2420,
    0x0F : 2425,
    0x10 : 2430,
    0x11 : 2435,
    0x12 : 2440,
    0x13 : 2445,
    0x14 : 2450,
    0x15 : 2455,
    0x16 : 2460,
    0x17 : 2465,
    0x18 : 2470,
    0x19 : 2475,
    0x1a : 2480,
    }

# change this LOG() if you want to print elsewhere than in the console
def LOG(msg=''):
    print('[CC2531]%s' % msg)

# returns the list of CC2531 plugged in
def get_CC2531():
    cc2531 = []
    ctx = usb1.USBContext()
    #
    for dev in ctx.getDeviceList(skip_on_error=True):
        if dev.getVendorID() == VID and dev.getProductID() == PID:
            #LOG(' found CC2531 @ USB bus %i and address %i' \
            #    % (dev.getBusNumber(), dev.getDeviceAddress()))
            cc2531.append(dev)
    #
    if cc2531 == []:
        LOG(' no CC2531 found (VID %x PID %x)' % (VID, PID))
        return []
    #
    try:
        manuf = cc2531[0].getManufacturer()
    except libusb1.USBError:
        #LOG(' cannot open USB device through libusb:' \
        #    ' add yourself in the "root" group or make an udev rule')
        return []
    # 
    return cc2531

# drives a CC2531 loaded with the default TI firmware sniffer
class CC2531(object):
    '''
    Drive a TI CC2531 802.15.4 dongle through python libusb1.
    ---
    It needs to be instanciated with a USB descriptor,
    such as one returned by get_CC2531() function.
    ---
    Basic methods allow to drive the dongle:
    .init() : re-init the dongle
    .config(chan) : tune the 802.15.4 dongle to the given channel
    .start_capture() : prepare the dongle to receive radio frames
    .read_data() : returns 802.15.4 frames within TI PSD structure
    .stop_capture() : stop the reception of radio frames
    ---
    See the test() function at the end of the file for basic use 
    of this class
    '''
    # from 0 (silent) to 3 (very verbose)
    DEBUG = 1
    #
    VID = VID
    PID = PID
    # only a single interface to control over
    IF = 0
    # only a single endpoint for receiving sniffed 802.15.4 packets
    DATA_EP = 3
    # data read settings
    DATA_BUFLEN = 1024 # data buffer size
    READ_TO = 1 # timeout in milliseconds
    #
    # CC2531 dongle internal configuration settings length
    CTRL_LEN = {
        192 : 256,
        198 : 1,
        210 : 1,
        }
    
    def __init__(self, CC2531_dev=None):
        # open communication to the USB device
        self.dev = CC2531_dev
        if not isinstance(self.dev, usb1.USBDevice):
            raise(Exception(' init with a CC2531 USB device obtained'\
                             ' from "get_CC2531" function'))
        #
        self._usb_desc = self.dev.getProduct()
        self._usb_bus = self.dev.getBusNumber()
        self._usb_addr = self.dev.getDeviceAddress()
        self._usb_serial = self.dev.getbcdDevice()
        #
        self._log('driving %s @ USB bus %i & address %i, with serial %i' \
                  % (self._usb_desc, self._usb_bus, self._usb_addr, self._usb_serial))
        #
        self.open()
        # init state
        self._sniffing = False
    
    def _log(self, msg=''):
        LOG('[%i] %s' % (self._usb_serial, msg))
    
    def open(self):
        self.com = self.dev.open()
        #
        # un-load possible kernel driver
        if platform.system() == 'Linux' and \
        self.com.kernelDriverActive(self.IF):
            if self.DEBUG:
                self._log('(open) unloading Linux Kernel driver')
            self.com.detachKernelDriver(self.IF)
        #
        # init communication with the device
        self.com.claimInterface(self.IF)
    
    def close(self):
        self.com.releaseInterface(self.IF)
        self.com.close()
    
    ###
    # dongle config sequence (captured from a windows session):
    # _set_config(0), ...
    # _get_ctrl(192), ...
    # _set_config(1), ...
    # _set_ctrl(197, 4), _get_ctrl(198) {3,}, _set_ctrl(201, 0), _set_ctrl(210, 0), _set_ctrl(210, 1), _set_ctrl(208, 0)
    # -> bulk transfer
    # _set_ctrl(209, 0), _set_ctrl(197, 0), _set_config(0), ...
    ###
    
    def _set_config(self, c=0):
        ret = self.com.controlWrite(0x00, 9, c, 0, 0)
        if self.DEBUG > 2:
            self._log('(_set_config, c %i) ret: %i' % (c, ret))
    
    def _get_ctrl(self, c=192):
        if c not in self.CTRL_LEN:
            l = 0x100
        else:
            l = self.CTRL_LEN[c]
        ret = self.com.controlRead(0xC0, c, 0, 0, l)
        if self.DEBUG > 2:
            self._log('(_get_ctrl, c %i) ret: %s' % (c, hexlify(ret)))
    
    def _wait_for_198(self, token):
        # send control frame with bRequest 198 until the dongle
        # respond with byte 0x04
        ret = ord(self.com.controlRead(0xC0, 198, 0, 0, 1))
        cnt = 1
        while ret != token:
            sleep(0.0624)
            ret = ord(self.com.controlRead(0xC0, 198, 0, 0, 1))
            cnt += 1
            if cnt >= 20:
                self._log('(_wait_for_198) cannot get 0x4 response')
                break
        if self.DEBUG > 2:
            self._log('(_wait_for_198) ret: %i' % ret)
    
    
    def _set_ctrl(self, c=197, i=4):
        if c not in self.CTRL_LEN:
            l = 0
        else:
            l = self.CTRL_LEN[c]
        ret = self.com.controlWrite(0x40, c, 0, i, l)
        if self.DEBUG > 2:
            self._log('(_set_ctrl, c %i, i %i) ret: %i' % (c, i, ret))
    
    def _set_chan(self, chan=0x0b):
        ret = self.com.controlWrite(0x40, 210, 0, 0, chr(min(255, max(0, chan))))
        if self.DEBUG > 2:
            self._log('(_set_chan) ret: %i' % ret)
        
    ###
    # macro sequences for controlling the CC2531 dongle
    ###
    
    def init(self):
        if self._sniffing:
            self.stop_capture()
        self._set_config(0)
        self._get_ctrl(192)
        if self.DEBUG > 1:
            self._log('(init) done')
    
    def config(self, chan=0xb):
        if self._sniffing:
            self.stop_capture()
            self.init()
        self._set_config(1)
        self._set_ctrl(197, 4)
        #
        # here we should do something useful 
        # for configuring the 802.15.4 channel number:
        self._wait_for_198(4)
        self._set_ctrl(201, 0)
        self._set_chan(chan)
        #
        if self.DEBUG:
            if chan in CHANNELS:
                self._log('tuning on channel 0x%x, frequency %i MHz' \
                          % (chan, CHANNELS[chan]))
            else:
                self._log('sending non-standard channel tuning control 0x%x' \
                          % chan)
        if self.DEBUG > 1:
            self._log('(config) done')
    
    def start_capture(self):
        self._sniffing = True
        self._set_ctrl(210, 1)
        self._set_ctrl(208, 0)
        if self.DEBUG > 1:
            self._log('(start_capture) done')
    
    def stop_capture(self):
        self._set_ctrl(209, 0)
        self._set_ctrl(197, 0)
        self._set_config(0)
        self._sniffing = False
        if self.DEBUG > 1:
            self._log('(stop_capture) done')
    
    def read_data(self):
        if self.DEBUG and not self._sniffing:
            self._log('(read_data) should start_capture() before read_data()')
        try:
            ret = self.com.bulkRead(self.DATA_EP, self.DATA_BUFLEN, self.READ_TO)
        except libusb1.USBError:
            # read timeout
            ret = ''
        if self.DEBUG > 1:
            info = ' - timeout' if not ret else ''
            self._log('(read_data) done%s' % info)
        return bytes(ret)
    

def test(cc=None, chan=0x0b):
    if cc is None:
        cc = CC2531(get_CC2531()[0])
    cc.init()
    cc.config(chan)
    cc.start_capture()
    cnt = 0
    while cnt < 5:
        print(hexlify(cc.read_data()))
        sleep(2)
        cnt += 1
    cc.stop_capture()
    return cc

