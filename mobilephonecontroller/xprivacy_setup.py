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

Script for the controller to import new coordinates on the phones
without importing the adb module
'''
import adb
import sys

def main():
    '''
    The main function needs 4 parameters:
    1. comma seperated coordinates
    2. comma seperated coordinates
    3. a video file name for the first coordinate pair
    4. a video file name for the second coordinate pair

    Steps:
    1. the screen records get sarted
    2. the screens of the smartphones get activated
    3. the coordinates get imported
    4. the screens get deactivated
    5. the screen records get stopped
    '''
    if len(sys.argv) < 5:
        #Test if the programm gets executed with to less parameters
        print('''The programme needs:
                 1. comma seperated coordinates
                 2. comma seperated coordinates
                 3. a video file name for the first coordinate pair
                 4. a video file name for the second coordinate pair
                 ''')
        sys.exit(1)

    co1 = sys.argv[1].split(',')
    co2 = sys.argv[2].split(',')
    video_names = [sys.argv[3], sys.argv[4]]
    smartphone_control = adb.adb()
    #Step 1
    pid_list = smartphone_control.start_screencast()
    #Step 2
    smartphone_control.activate_screen()
    #Step 3
    smartphone_control.xprivacy_set_fake_location([co1, co2])
    #Step 4
    smartphone_control.sleep()
    #Step 5
    smartphone_control.stop_screencast(video_names, pid_list)

if __name__ == '__main__':
    main()
