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
# * File Name : receiver.py
# * Created : 2013-11-13
# * Authors : Benoit Michau, ANSSI
# *--------------------------------------------------------
# */
#!/usr/bin/python2
#
###
# 802.15.4 monitor based on Texas Instruments CC2531 USB dongle
#
# uses libusb1
# http://www.libusb.org/
# and python-libusb1
# https://github.com/vpelletier/python-libusb1/
###

import os
import socket
import signal
from struct import pack
from time import time, sleep
from CC2531 import *

# export filtering
__all__ = ['receiver']


CC2531.DEBUG = 0
T_PAUSE = 0.05

# change this LOG() if you want to print elsewhere than in the console
def LOG(msg=''):
    print('[receiver]%s' % msg)

def siesta():
    sleep(T_PAUSE)

class receiver(object):
    '''
    Drive a single TI CC2531 802.15.4 dongle.
    It makes use of the USB driver through a CC2531 instance. 
    ---
    Receive sequentially on each 802.15.4 channel set in .CHAN_LIST 
    for a period of .CHAN_PERIOD second(s)
    ---
    Each 802.15.4 frame received is wrapped into a structure
    and forwarded to a UNIX file or UDP server, as defined in .SOCK_ADDR
    ---
    The structure is a set of TLV fields:
    Tag : uint8, Length : uint16, Value : char*[Length]
    T=0x01, 802.15.4 channel, uint8
    T=0x02, epoch time at frame reception, ascii encoded
    T=0x03, position at frame reception (if positionning server -GPS- available)
            modify .get_position() method to adapt it to work with your GPS
            current .get_position() method uses the gps.py file to read GPS info
            from a /dev/ttyUSB serial GPS
    T=0x10, 802.15.4 frame within TI USB frame structure (default CC2531 behavior)
    T=0x20, 802.15.4 frame
    ---
    Each of this TLV structure is prefixed with a uint32 total length indication
    '''
    # debug level
    DEBUG = 1
    # for interrupt handler and looping control
    _THREADED = False
    _STOP_EVENT = None
    #
    # server address to send frames to
    # str -> file socket, tuple -> udp socket
    #SOCK_ADDR = '/tmp/cc2531_sniffer'
    SOCK_ADDR = ('127.10.0.1', 2154)
    
    # 802.15.4 channels to walk over
    CHAN_LIST = CHANNELS.keys()
    # time (in second) before changing the channel
    CHAN_PERIOD = 1
    
    # GPS service for get_position()
    # check gps.py for dealing with GPS running over serial USB and NMEA infos
    GPS = None
    
    def __init__(self, cc2531):
        self._cc = cc2531
        if not isinstance(self._cc, CC2531):
            raise(Exception('init with a CC2531 instance'))
        # init socket connectivity
        self._init_sock()
        # init dongle
        self._cc.init()
        self._chan = 0
        self._listening = False
        # catch SIGINT
        if not self._THREADED:
            def handle_int(signum, frame):
                self.stop()
                self._log('SIGINT: quitting')
            signal.signal(signal.SIGINT, handle_int)
    
    def _log(self, msg=''):
        LOG('[%i:%i:%i] %s' % (self._cc._usb_bus, self._cc._usb_addr, \
                               self._cc._usb_serial, msg))
    
    def _init_sock(self):
        if isinstance(self.SOCK_ADDR, str):
            self._init_file_sock()
        elif isinstance(self.SOCK_ADDR, tuple) and len(self.SOCK_ADDR) == 2 \
        and isinstance(self.SOCK_ADDR[0], str) and isinstance(self.SOCK_ADDR[1], int):
            self._init_udp_sock()
        else:
            raise(Exception('bad SOCK_ADDR parameter'))
    
    def _init_file_sock(self):
        # if needed, create file sock
        if not os.path.exists(self.SOCK_ADDR):
            raise(Exception('file socket server does not exist yet'))
        self._sk = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        if self.DEBUG:
            self._log('forwarding to file socket %s' % self.SOCK_ADDR)
    
    def _init_udp_sock(self):
        self._sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.DEBUG:
            self._log('forwarding to UDP socket %s' % list(self.SOCK_ADDR))
    
    def send(self, data=''):
        if not hasattr(self, '_sk') or not isinstance(data, str):
            return 0
        return self._sk.sendto(data, self.SOCK_ADDR)
    
    def get_position(self, *args, **kwargs):
        #pass
        if hasattr(self, 'GPS') and hasattr(self.GPS, 'get_last_info'):
            #print self.GPS.infos
            return self.GPS.get_last_info('GPRMC')
    
    def stop(self):
        if self._listening:
            self._listening = False
            siesta()
            self._cc.stop_capture()
        self._cc.init()
        #siesta()
        self._cc.close()
        #self.send( '\0' )
        self._sk.close()
    
    def looping(self):
        if not self._listening:
            return False
        else:
            if not self._THREADED:
                return True
            elif hasattr(self._STOP_EVENT, 'is_set') \
            and not self._STOP_EVENT.is_set():
                return True
            return False
    
    def listen(self):
        self._listening = True
        self._log('start listening on channel(s): %s' % self.CHAN_LIST)
        #
        # multi-channel hopping monitor
        if len(self.CHAN_LIST) > 1:
            while self.looping() :
                for c in self.CHAN_LIST:
                    if self.looping():
                        self._chan = c
                        if self.DEBUG:
                            self._log('sniffing on channel %i' % self._chan)
                        self._cc.init()
                        self._cc.config(c)
                        self._cc.start_capture()
                        T0 = time()
                        while self.looping() and (time()-T0 < self.CHAN_PERIOD):
                            self.read_frames()
                        self._cc.stop_capture()
        #
        # single channel monitor
        elif len(self.CHAN_LIST) == 1:
            self._chan = self.CHAN_LIST[0]
            if self.DEBUG:
                self._log('sniffing on channel %i' % self._chan)
            self._cc.init()
            self._cc.config(self._chan)
            self._cc.start_capture()
            while self.looping():
                self.read_frames()
            self._cc.stop_capture()
                
    def read_frames(self):
        data = self._cc.read_data()
        if len(data) == 0:
            siesta()
        # multiple radio frames can be concatenated into a single USB bulk 
        # transfer: they are split here
        while len(data) > 7:
            l = unpack('<H', data[1:3])[0]
            self.forward(data[:l+3])
            data = data[l+3:]
    
    def forward(self, data=5*'\0'):
        # add channel TLV
        dgram = [ '\x01\x00\x01%s' % chr(self._chan) ]
        # add time TLV
        t = str(time())
        dgram.append( '\x02%s%s' % (pack('!H', len(t)), t) )
        # eventually add position TLV
        p = self.get_position()
        if p:
            dgram.append( '\x03%s%s' % (pack('!H', len(p)), str(p)) )
        # add TI USB frame structure
        dgram.append( '\x10%s%s' % (pack('!H', len(data)), data) )
        #
        # send dgram frame to the server
        frame = ''.join(dgram)
        frame_len = pack('!I', len(frame))
        self.send( ''.join((frame_len, frame)) )
        #print('forward msg: %s' % frame.encode('hex')) 
