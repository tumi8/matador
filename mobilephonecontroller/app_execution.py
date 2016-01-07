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

Script for the controller to start the applications and send 4 messages
without importing the adb module.
'''
import adb
import time
import sys

def main():
    '''
    The main function needs 3 parameters:
    1. an application name
    2. a video name for the first phone
    3. a video name for the second phone

    Steps:
    1. the screen records get sarted
    2. the screens of the smartphones get activated
    3. the firewalls get opened for the application
    4. the wifi gets activated on the phones
    5. the application gets started on the phones
    6. 4 messages get sent
    7. an additonal timeout is waited in the messenger
    8. the application gets closed on the phones
    9. the firewalls get closed
    10. the wifi gets deactivated on each phone
    11. the screens get deactivated
    12. the screen records get stopped
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
    smartphone_control.firewall_open_uid(app)
    #Step 4
    smartphone_control.start_wifi()
    #Step 5
    smartphone_control.start_application(app)
    #Step 6
    #The adb module takes turns between the phones by itself
    i = 0
    while i <4:
        smartphone_control.send_message(app)
        time.sleep(5)
        i = i+1
    #Step 7
    smartphone_control.wait_in_messenger(app)
    #Step 8
    smartphone_control.close_application(app)
    #Step 9
    smartphone_control.firewall_close_uid(app)
    #Step 10
    smartphone_control.stop_wifi()
    #Step 11
    smartphone_control.sleep()
    #Step 12
    smartphone_control.stop_screencast(video_names, pid_list)

if __name__ == '__main__':
    main()
