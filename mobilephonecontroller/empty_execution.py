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

Script for the controller that starts nothing but waits 60s
without importing the adb module.
'''
import adb
import time
import sys

def main():
    '''
    The main function needs 3 parameters to execute it similar to the app_execution script:
    1. an application name (nothing is done with it)
    2. a video name for the first phone
    3. a video name for the second phone

    Steps:
    1. the screen records get sarted
    2. the screens of the smartphones get activated
    3. the wifi gets activated on the phones
    4. 60s are waited
    5. the wifi gets deactivated on each phone
    6. the screens get deactivated
    7. the screen records get stopped
    '''
    if len(sys.argv) < 4:
        #Test if the programm gets executed with to many parameters
        print('''
              The programme needs:
                1. an application name
                2. a video name for the first phone
                3. a video name for the second phone
                ''')
        sys.exit(1)

    app = sys.argv[1]
    video_names = [sys.argv[2], sys.argv[3]] 
    smartphone_control = adb.adb()
    #Step 1
    pid_list = smartphone_control.start_screencast()
    #Step 2
    smartphone_control.activate_screen()
    #Step 3
    smartphone_control.start_wifi()
    #Step 4
    time.sleep(60)
    #Step 5
    smartphone_control.stop_wifi()
    #Step 6
    smartphone_control.sleep()
    #Step 7
    smartphone_control.stop_screencast(video_names, pid_list)

if __name__ == '__main__':
    main()
