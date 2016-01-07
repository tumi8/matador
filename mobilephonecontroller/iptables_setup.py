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

Script for the controller to setup iptables on the phones
without importing the adb module
'''
import adb
import sys

def main():
    '''
    The main function does not need any parameters and only loads the adb clas
    and exectuted the firewall_set_up function
    '''
    if len(sys.argv) < 1:
        #Test if the programm gets executed with to less parameters
        print('The programme needs no parameters')
        sys.exit(1)

    smartphone_control = adb.adb()
    smartphone_control.firewall_set_up()

if __name__ == '__main__':
    main()
