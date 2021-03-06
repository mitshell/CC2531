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
# * File Name : interpreter.py
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
#
# This is the part which will read the feedback from receiver() instances
# and interpret it for some information gathering / wardriving.
# It requires libmich and its IEEE802154 format descriptor.
#

import socket
import os
import signal
import select
import errno
from struct import unpack
from time import strftime, localtime, sleep
from binascii import hexlify
from CC2531 import CHANNELS
from libmich.formats.IEEE802154 import TI_USB, TI_CC, IEEE802154

# export filtering
__all__ = ['interpreter']

# this is to customize another 802.15.4 frame decoder
DECODER = IEEE802154
# this is the default CC2531 behavior
DECODER.PHY_INCL = False
DECODER.FCS_INCL = False

def LOG(msg=''):
    print('[interpreter] %s' % msg)

class interpreter(object):
    # debug level
    DEBUG = 1
    # for interrupt handler and looping control
    _THREADED = False
    _STOP_EVENT = None
    #
    #SOCK_ADDR = '/tmp/cc2531_sniffer'
    SOCK_ADDR = ('127.10.0.1', 2154)
    #
    # select loop and socket recv settings
    SELECT_TO = 0.5
    SOCK_BUFLEN = 1024
    #
    # interpreter output (stdout and/or file)
    OUTPUT_STDOUT = True
    #OUTPUT_FILE = None
    OUTPUT_FILE = '/tmp/cc2531_sniffer'
    # output even when the FCS check fails
    FCS_IGNORE = False
    
    def __init__(self):
        # create the socket server
        if isinstance(self.SOCK_ADDR, str):
            self._create_file_serv()
        elif isinstance(self.SOCK_ADDR, tuple) and len(self.SOCK_ADDR) == 2 \
        and isinstance(self.SOCK_ADDR[0], str) and isinstance(self.SOCK_ADDR[1], int):
            self._create_udp_serv()
        else:
            raise(Exception('bad SOCK_ADDR parameter'))
        #
        # catch CTRL+C
        if not self._THREADED:
            def serv_int(signum, frame):
                self.stop()
                LOG('SIGINT: quitting')
            signal.signal(signal.SIGINT, serv_int)
        #
        # check output parameters
        if self.OUTPUT_FILE:
            try:
                fd = open(self.OUTPUT_FILE, 'a+')
                fd.write(''.join((20*'#', '\n', '# 802.15.4 interpreter session\n', 
                                  '# %s\n' % strftime('%Y-%m-%d %H:%M:%S', localtime()), 
                                  20*'#', '\n')))
            except IOError:
                self._log('cannot write output to %s' % self.OUTPUT_FILE)
                self.OUTPUT_FILE = None
        #
        # init empty message struct
        self._cur_msg = {}
        self._processing = False
    
    def _log(self, msg=''):
        LOG(msg)
    
    def _create_file_serv(self):
        try:
            os.unlink(self.SOCK_ADDR)
        except OSError:
            if os.path.exists(self.SOCK_ADDR):
                raise(Exception('cannot clean %s' % self.SOCK_ADDR))
        # serv on the file
        sk = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sk.bind(self.SOCK_ADDR)
        except socket.error:
            raise(Exception('cannot clean %s' % addr))
        #
        if self.DEBUG:
            self._log('server listening on %s' % self.SOCK_ADDR)
        self._sk = sk
    
    def _create_udp_serv(self):
        # serv on UDP port
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sk.bind(self.SOCK_ADDR)
        except socket.error:
            raise(Exception('cannot bind on UDP port %s' % list(self.SOCK_ADDR)))
        #
        if self.DEBUG:
            self._log('server listening on %s' % list(self.SOCK_ADDR))
        self._sk = sk
    
    def stop(self):
        self._processing = False
        sleep(0.2)
        self._sk.close()
    
    def output(self, line=''):
        if self.OUTPUT_STDOUT:
            print(line)
        if self.OUTPUT_FILE:
            try:
                fd = open(self.OUTPUT_FILE, 'a')
            except IOError:
                pass
            else:
                fd.write('%s\n' % line)
                fd.close()
    
    def looping(self):
        if not self._processing:
            return False
        else:
            if not self._THREADED:
                return True
            elif hasattr(self._STOP_EVENT, 'is_set') \
            and not self._STOP_EVENT.is_set():
                return True
            return False
    
    def process(self):
        # loop on recv()
        self._processing = True
        #
        while self.looping():
            try:
                r = select.select([self._sk], [], [], self.SELECT_TO)[0]
            except select.error as e:
                if e.args[0] == errno.EINTR:
                    self._processing = False
                else:
                    pass
            else:
                for sk in r:
                    msg = sk.recv(self.SOCK_BUFLEN)
                    #print('UDP msg: %s' % msg.encode('hex'))
                    while len(msg) >= 4:
                        frame_len = unpack('!I', msg[:4])[0]
                        frame = msg[4:4+frame_len]
                        self.interpret(frame)
                        msg = msg[4+frame_len:]
    
    def interpret(self, msg=''):
	    #print('interpret msg: %s' % msg.encode('hex'))
        # init message structure
        self._cur_msg = {}
        # parse it into the structure
        while len(msg) > 0:
            msg = self._get_tlv(msg)
        # output it nicely
        if 'frame' in self._cur_msg \
        and 'timestamp' in self._cur_msg \
        and 'channel' in self._cur_msg:
            if self._cur_msg['FCS_OK']:
                fcschk = 'OK'
            else:
                fcschk = 'error'
            self.output('[+] frame received (FCS %s): %s' \
                        %  (fcschk, strftime('%Y-%m-%d %H:%M:%S',
                                    localtime(self._cur_msg['timestamp']))))
            if 'position' in self._cur_msg:
                self.output('position (GPRMC): %s' % self._cur_msg['position'])
            self.output('channel: %i, %i MHz' % (self._cur_msg['channel'],
                        CHANNELS[self._cur_msg['channel']]))
            if 'RSSI' in self._cur_msg:
                self.output('RSSI: %i' % self._cur_msg['RSSI'])
            self.output('IEEE 802.15.4 frame: %s' % hexlify(self._cur_msg['frame']))
            try:
                self.output('IEEE 802.15.4 MAC:\n%s\n' % self._cur_msg['MAC'].show())
            except:
                self.output('IEEE 802.15.4 MAC: -decoding error-\n')
    
    def _get_tlv(self, msg=''):
        if len(msg) > 2:
            T, L = unpack('!BH', msg[0:3])
            if L and len(msg) >= 3+L:
                V = msg[3:3+L]
            elif L:
                if self.DEBUG:
                    self._log('corrupted message')
                return ''
            self._interpret_TV(T, V)
            return msg[3+L:]
        else:
            if self.DEBUG:
                self._log('corrupted message')
            return ''
    
    def _interpret_TV(self, T=0, V=''):
        if T == 1:
            self._cur_msg['channel'] = ord(V[0])
        elif T == 2:
            self._cur_msg['timestamp'] = float(V)
        elif T == 3:
            # TODO: check exactly how GPS position is computed
            self._cur_msg['position'] = V
        elif T == 0x10:
            # TI_PSD structure
            self._interpret_TI_USB(V)
        elif T == 0x20:
            self._cur_msg['frame'] = V
            mac = self.DECODER()
            mac.parse(V)
            self._cur_msg['MAC'] = mac
    
    def _interpret_TI_USB(self, V=''):
        usb = TI_USB()
        try:
            usb.map(V)
        except:
            return
        # process only 802.15.4 frames with correct checksum,
        # or process all frames if FCS is ignored
        if self.FCS_IGNORE or usb.TI_CC.FCS():
            self._cur_msg['dev_ts'] = usb.TS()
            self._cur_msg['RSSI'] = usb.TI_CC.RSSI()
            self._cur_msg['frame'] = usb.TI_CC.Payload()
            self._cur_msg['FCS_OK'] = usb.TI_CC.FCS()
            mac = DECODER()
            try:
                mac.parse(self._cur_msg['frame'])
            except:
                mac = ''
            self._cur_msg['MAC'] = mac
