'''
Copyright 2015 Johannes Zirngibl

This file is part of MATAdOR.

MATAdOR is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

MATAdOR is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

Network_Check on each router.
Checks if the tunnel and network setup works.
Reconfigures the DHCP server and other configurations afterwards
'''
import subprocess
import os
import sys
import configparser


class MyException(Exception):
    '''
    Exception to raise if somethng returned unsuccessful
    '''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def check():
    '''
    The script executes multiple commands listed in the config file
    and waits actively if they return successful
    '''
    direc = os.path.dirname(__file__)
    if direc != '':
        direc = direc + '/'
    config = configparser.ConfigParser()
    config.read(direc+'network_check.ini')
    steps = int(config['general']['steps'])
    i = 1
    while i <= steps:
        command = config['step'+str(i)]['command']

        subprocess.check_call(command, shell=True)

        i = i+1

def main():
    '''
    No Parameters are given
    '''
    if len(sys.argv) < 1:
        #Test if the programm gets executed with to less parameters
        print('The programme needs a hostname to run')
        sys.exit(1)

    check()

if __name__ == '__main__':
    main()
