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
# * File Name : gps.py
# * Created : 2013-11-13
# * Authors : Benoit Michau, ANSSI
# *--------------------------------------------------------
# */
#!/usr/bin/python2
#
###
# GPS serial reader
#
# reads over /dev/ttyUSB port for NMEA information
###

import select
import signal
import serial
from time import sleep
#from binascii import *

# export filtering
__all__ = ['GPS_reader']

def LOG(msg=''):
    print('[GPS_reader]%s' % msg)

class GPS_reader(object):
    # debug level
    DEBUG = 1
    # for interrupt handler and looping control
    _THREADED = False
    _STOP_EVENT = None
    # serial port
    PORT = '/dev/ttyUSB0'
    BAUDRATE = 9600
    # number of last NMEA info to store
    NMEA_NUM = 3
    # type of NMEA info to collect
    NMEA_TYPE = ("GPBOD", "GPBWC", "GPGGA", "GPGLL", "GPGSA", "GPGSV", "GPHDT",
                 "GPR00", "GPRMA", "GPRMB", "GPRMC", "GPRTE", "GPTRF", "GPSTN",
                 "GPVBW", "GPVTG", "GPWPL", "GPXTE", "GPZDA")
    
    def __init__(self):
        try:
            self._ser = serial.Serial(port=self.PORT, baudrate=self.BAUDRATE)
        except:
            LOG('[ERR] cannot open %s' % self.PORT)
            self._ser = None
        #
        self.infos = {}
        for nmea_t in self.NMEA_TYPE:
            self.infos[nmea_t] = []
        #
        self._listening = False
        self._reading = False
        #
        if self._ser:
            LOG(' reading position information over %s' % self.PORT)
        #
        if not self._THREADED:
            def handle_int(signum, frame):
                self.stop()
                LOG(' SIGINT: quitting')
            signal.signal(signal.SIGINT, handle_int)
        
    def stop(self):
        self._listening = False
        if self._ser:
            while self._reading:
                sleep(0.001)
            self._ser.close()
    
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
        if not self._ser:
            return
        self._listening = True
        while self.looping():
            try:
                self._reading = True
                l = self._ser.readline()
                self._reading = False
            # catch various errors that happen when the serial port is not
            # available in some way
            except (OSError, ValueError, serial.SerialException):
                break
            else:
                self.process(l)
    
    def process(self, buf='\n'):
        if self.DEBUG > 1:
            LOG(' process buf: %s' % buf) 
        # grep NMEA_TYPE we want to get
        nmea_t = buf[1:6]
        if nmea_t in self.NMEA_TYPE:
            self.infos[nmea_t].append(buf[7:-2])
            if len(self.infos[nmea_t]) > self.NMEA_NUM:
                self.infos[nmea_t].remove( self.infos[nmea_t][0] )
            if self.DEBUG:
                LOG(' got %s: %s' % (nmea_t, buf[7:-2]))
    
    def get_last_info(self, nmea_t='GPRMC'):
        if not self._ser:
            return ''
        if nmea_t in self.NMEA_TYPE:
            if len(self.infos[nmea_t]):
                return self.infos[nmea_t][-1]

