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

Script for the controller to bring the phones to a clean state
after an exception without importing the adb module.
'''
import adb
import sys

def main():
    '''
    The main function does not need any parameters.
    It loads the adb clas and goes through the following steps:
    1. stop the wifi
    2. close all apps
    3. deactivate the screens
    '''
    if len(sys.argv) < 1:
        #Test if the programm gets executed with to less parameters
        print('The programme needs no parameters')
        sys.exit(1)

    smartphone_control = adb.adb()
    #Step 1
    smartphone_control.stop_wifi()
    #Step 2
    apps = smartphone_control.get_list_of_available_apps()
    for app in apps:
        smartphone_control.close_application(app)
    #Step 3
    smartphone_control.sleep()

if __name__ == '__main__':
    main()
