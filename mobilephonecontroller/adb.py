#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

Combination of all necessary functions for the smartphone controller.
'''
import subprocess
import time
import configparser
import os
import sys
import signal

class adb():
    '''
    Class with all smartphone ADB activities scripted
    Display:
        1. turn display on
        2. turn display off
        3. start screen record
        4. stop screen record and copy the result to the controller
    Network:
        1. start wifi
        2. stop wifi
        3. Setup firewall initially
        4. Open firewall for one appliation
        5. Close firewall for one application
        6. Tear down firewall completly
    Application:
        1. Start applications
        2. Send messages
        3. Close applications
    '''
    #An .ini file is used to exclude all Parameters
    direc = os.path.dirname(__file__)
    if direc != '':
        direc = direc+'/'

    config = configparser.ConfigParser()
    config.read(direc + 'adb.ini')

    '''
    The .ini file can hold a list of devices. Sending messages is mainly
    designed for two devices, but more devices should be possible
    A possible scenario could be a group chat with multiple members,
    which send messages in turn
    '''
    devices = config['general']['devices'].split(', ')
    applications = config['general']['applications'].split(', ')

    #The switch is used to send the messages in turn
    switch = 0

    def get_list_of_available_apps(self):
        '''
        returns the application list from the config file to other modules if necessary
        '''
        return self.applications

    def get_list_of_available_devices(self):
        '''
        returns the device list from the config file to other modules if necessary
        '''
        return self.devices

    def get_number_of_available_devices(self):
        '''
        returns the number of available devices from the config file to other modules if necessary
        '''
        return len(self.devices)

    def start_wifi(self):
        '''
        Starts the wifi on all devices listed in the .ini file one after another
        '''
        for device in self.devices:
            subprocess.check_call('adb -s '+ device + ' shell "su -c svc wifi enable"',
                                  shell=True)
        time.sleep(3.5)
        assumption = False
        for device in self.devices:
            if subprocess.check_output('adb -s '+ device + ' shell ping -c 5 -i 0.2 8.8.8.8',
                                       shell=True) == b'connect: Network is unreachable\r\n':
                assumption = True
        tries = 1
        while assumption:
            if tries < 3:
                assumption = False
                for device in self.devices:
                    subprocess.check_call('adb -s ' + device + ' shell "su -c svc wifi disable"',
                                          shell=True)
                    time.sleep(1)
                    subprocess.check_call('adb -s '+ device + ' shell "su -c svc wifi enable"',
                                          shell=True)
                time.sleep(2+tries*2)
                for device in self.devices:
                    command = 'adb -s '+ device + ' shell ping -c 5 -i 0.2 8.8.8.8'
                    network_down = b'connect: Network is unreachable\r\n'
                    if subprocess.check_output(command, shell=True) == network_down:
                        assumption = True
                tries = tries+1
            else:
                sys.exit(3)

    def stop_wifi(self):
        '''Stops the wifi on all devices listed in the .ini file one after another.'''
        for device in self.devices:
            subprocess.check_call('adb -s ' + device + ' shell "su -c svc wifi disable"',
                                  shell=True)

    def activate_screen(self):
        '''
        To activate the screen pressing the power button gets simulated with the keyevent 26.
        (http://developer.android.com/reference/android/view/KeyEvent.html).
        Afterwards swiping from the bottom to the top of the screen gets simulated
        to unlock the screen.
        '''
        for device in self.devices:
            subprocess.check_call('adb -s {0} shell input keyevent 26'.format(device),
                                  shell=True)

        for device in self.devices:
            maxX = int(self.config[device]['maxX'])
            maxY = int(self.config[device]['maxY'])
            command = 'adb -s {0} shell input swipe {1} {2} {3} {4}'.format(device, str((maxX)/2),
                                                                            str(maxY-100),
                                                                            str((maxX)/2),
                                                                            str((maxY)/5)),
            subprocess.check_call(command, shell=True)

    def sleep(self):
        '''
        To deactivate the screen and put the device to sleep the keyevent 223 is used.
        (http://developer.android.com/reference/android/view/KeyEvent.html)
        '''
        for device in self.devices:
            subprocess.check_call('adb -s {0} shell input keyevent 223'.format(device),
                                  shell=True)

    def start_application(self, app):
        '''
        Starting an application is subdivided into 3 steps:
            1. The application gets started. Therefore each Android application holds at least
               one main activity. This activity can get triggered with the am command.
            2. A tap on the conversation is simulated. Therefore the coordinates of this tap have
               to be available in the .ini file for each application.
            3. A tap on the Text Input Field is simulated. Therefore the coordinates of this tap
               have to be available in the .ini file  for each application.
        This method needs an application name as input.
        '''
        startActivity = self.config[app]['startActivity']
        startupTime = float(self.config[app]['startupTime'])
        conversationCoordinates = self.config[app]['conversationCoordinates']
        textInputFieldCoordinates = self.config[app]['textInputFieldCoordinates']

        for device in self.devices:
            subprocess.check_call('adb -s {0} shell am start {1}'.format(device, startActivity),
                                  shell=True)

        time.sleep(startupTime)

        for device in self.devices:
            command = 'adb -s {0} shell input tap {1}'.format(device, conversationCoordinates)
            subprocess.check_call(command, shell=True)

        time.sleep(2)

        for device in self.devices:
            command = 'adb -s {0} shell input tap {1}'.format(device, textInputFieldCoordinates)
            subprocess.check_call(command,
                                  shell=True)

    def close_application(self, app):
        '''
        Each application has a name on Android. With this name, a force stop is possible
        This method needs an application name as input,.
        '''
        name = self.config[app]['applicationName']
        for device in self.devices:
            subprocess.check_call('adb -s {0} shell am force-stop {1}'.format(device, name),
                                  shell=True)

    def start_screencast(self):
        '''
        Starts the screencast and saves the pids of the accoriding processes in a list
        and returns the list at the end.
        The pids are used to stop the process in the stop_screencast activity
        '''
        pid_list = []
        for device in self.devices:
            command = 'adb -s {0} shell '.format(device)
            command = command + 'screenrecord --size 360x640 --bit-rate 1000000 /sdcard/video.mp4'
            pid_list = pid_list + [subprocess.Popen(command,
                                                    shell=True,
                                                    preexec_fn=os.setsid).pid]

        return pid_list

    def stop_screencast(self, filenames, pid_list):
        '''
        The screencast stops automatically after 3 min.
        If the recording time was smaller, the processes get interupted with SIGINT.
        '''
        for device in self.devices:
            try:
                os.killpg(pid_list.pop(0), signal.SIGINT)
            except ProcessLookupError:
                pass
            time.sleep(1)
            command = 'adb -s {0} pull /sdcard/video.mp4 {1}'.format(device, filenames.pop(0))
            subprocess.check_call(command, shell=True)

    def send_message(self, app):
        '''
        Each application has a name on Android. With those a force stop is possible.
        This method needs an application name as input.
        '''
        SendButtonCo = self.config[app]['SendButtonCoordinates']
        text_source = self.direc + self.config['general']['text_source']
        text = subprocess.check_output(text_source, shell=True).decode("utf-8")
        '''
        The input text command of the Android shell accepts strings
        but some characters have to be replaced.
        This list works for the Death of a salesman input.
        Perhaps it needs to be expanded for other text sources.
        '''
        text = text.replace(' ', '%s')
        text = text.replace('’', '\\\'')
        text = text.replace('‘', '\\\'')
        text = text.replace('—', '-')
        text = text.replace('"', '\"')
        text = '\"' + text + '\"'
        text = text.replace(';', '\;')

        device = self.devices[self.switch]

        subprocess.check_call('adb -s {0} shell input text {1}'.format(device, text),
                              shell=True)

        subprocess.check_call('adb -s {0} shell input tap {1}'.format(device, SendButtonCo),
                              shell=True)

        self.switch = (self.switch+1)%len(self.devices)

    def wait_in_messenger(self, app):
        '''
        Sometimes the 5s timeout after each meassage is not enough to recevie the message
        on the second phone.
        To make sure the messages receive in the same measurement,
        a fixed timeout can be waited at the end.
        '''
        waittime = self.config[app]['waittime']
        time.sleep(int(waittime))

    def xprivacy_set_fake_location(self, list_of_coordinates):
        '''
        The XPrivacy Pro version supports Exporting and Importing configutations as an xml file.
        There are actvies for both functions.
        The import function does not accept a file directly, but opens a file explorer with
        the recently imported file.
        Therefore this method copies the xml file
        everytime with the same name to the same directory.
        This has to be done unfortunately once by hand before.
        Steps:
            1. Create the XML file with the new longitutde and latitude
            2. Push it to all devices
            3. Start the Xprivacy import activity
            4. Tap on the pushed file
            5. Tap on ok
            6. Tap on ok again
        '''
        app_list = self.config['general']['applications'].split(', ')

        directory = self.config['xprivacy']['directory']
        fileCoordinates = self.config['xprivacy']['fileCoordinates']
        okCoordinates = self.config['xprivacy']['okCoordinates']

        #The xprivacy support is optional
        devices_with_xprivacy_support = [device for device in self.devices
                                         if self.config[device].getboolean('xprivacy')]
        if len(devices_with_xprivacy_support) != 0:
            for device in devices_with_xprivacy_support:
                '''
                The config xml has to holds only the values that want to be changed.
                Therefore this creates the minimal file possible
                '''
                #Step1
                coords = list_of_coordinates.pop(0)
                file = open('xprivacy_coordinates.xml', 'w')
                file.write('<XPrivacy>')
                file.write('<Setting Id="" Type="" Name="Latitude" Value="'+str(coords[0]) + '" />')
                file.write('<Setting Id="" Type="" Name="Longitude" Value="'+str(coords[1])+ '" />')
                file.write('</XPrivacy>')
                file.close()

                #Step2
                app_uid_list = [self.config[device][app+'_uid'] for app in app_list]
                command = 'adb -s {0} push {1} {2}{1}'.format(device,
                                                              'xprivacy_coordinates.xml',
                                                              directory)
                subprocess.check_call(command, shell=True)

                #Step3
                command = 'adb -s ' + device + ' shell '
                command = command +'am start -a biz.bokhorst.xprivacy.action.IMPORT --eia  UidList '
                command = command + ','.join(app_uid_list) + ' --ez Interactive true'
                subprocess.check_call(command, shell=True)

            #statring the activity takes some time
            time.sleep(6)
            for device in devices_with_xprivacy_support:
                #Step4
                command = 'adb -s {0} shell input tap {1}'.format(device, fileCoordinates)
                subprocess.check_call(command, shell=True)

                #Step5
                command = 'adb -s {0} shell input tap {1}'.format(device, okCoordinates)
                subprocess.check_call(command, shell=True)

            #importing the file takes some time
            time.sleep(1)
            for device in devices_with_xprivacy_support:
                #Step6
                command = 'adb -s {0} shell input tap {1}'.format(device, okCoordinates)
                subprocess.check_call(command, shell=True)

            time.sleep(1)
            for device in devices_with_xprivacy_support:
                command = 'adb -s {0} shell am force-stop biz.bokhorst.xprivacy'.format(device)
                subprocess.check_call(command, shell=True)

    def firewall_set_up(self):
        '''
        Set up firewall:
        '''
        white_list = self.config['iptables'].getboolean('white_list')
        chain = self.config['iptables']['chain']
        uid_range = self.config['iptables']['range']
        selected_uid = self.config['iptables']['selected_uid'].split(', ')
        for device in self.devices:
            if self.config[device].getboolean('iptables'):
                command = 'adb -s {0} shell su -c '.format(device)
                command = command + '"iptables -N {0}; iptables -I OUTPUT -j {0}"'.format(chain)
                subprocess.check_call(command, shell=True)
                if white_list:
                    command = 'adb -s {0} shell su -c '.format(device)
                    command = command + '"iptables -A {0} -m owner --uid-owner {1} -j REJECT --reject-with icmp-port-unreachable"'.format(chain, uid_range)
                    subprocess.check_call(command, shell=True)

                    for uid in selected_uid:
                        command = 'adb -s {0} shell su -c '.format(device)
                        command = command + '"iptables -I {0} -m owner --uid-owner {1} -j RETURN"'.format(chain, uid)
                        subprocess.check_call(command, shell=True)
                        time.sleep(1)

                else:
                    command = 'adb -s {0} shell su -c '.format(device)
                    command = command + '"iptables -A {0} -m owner --uid-owner {1} -j RETURN"'.format(chain, uid_range)
                    subprocess.check_call(command, shell=True)

                    for uid in selected_uid:
                        command = 'adb -s {0} shell su -c '.format(device)
                        command = command + '"iptables -I {0} -m owner --uid-owner {1} -j REJECT --reject-with icmp-port-unreachable"'.format(chain, uid)
                        subprocess.check_call(command, shell=True)
                        time.sleep(1)

    def firewall_stop_complete(self):
        '''
        Deletes the added chain and removes added rules.
        '''
        chain = self.config['iptables']['chain']
        for device in self.devices:
            if self.config[device].getboolean('iptables'):
                command = 'adb -s {0} shell su -c '.format(device)
                command = command + '"iptables -F {0}; iptables -D OUTPUT -j {0} ; iptables -X {0} "'.format(chain)
                subprocess.check_call(command, shell=True)
        time.sleep(1)

    def firewall_open_uid(self, app):
        '''
        If the device supports an iptables firewall this method executes the iptables command
        that is needed to open the firewall for the application
        Android assigns uid to applications, therefore an owner match can be used
        to open the firewall for a particular application.
        This method needs an application name as input.
        '''
        for device in self.devices:
            if self.config[device].getboolean('iptables'):
                dev_app_uid = self.config[device][app+'_uid']
                chain = self.config['iptables']['chain']
                subprocess.check_call('adb -s {0} shell su -c "iptables -I {1} -m owner --uid-owner {2} -j RETURN"'.format(device, chain, dev_app_uid),
                                      shell=True)
        time.sleep(3)

    def firewall_close_uid(self, app):
        '''
        If the device supports an iptables firewall this method executes the iptables command
        that is needed to close the firewall for the application
        Android assigns uid to applications, therefore an owner match can be used
        to close the firewall for a particular application.
        This method needs an application name as input.
        '''
        for device in self.devices:
            if self.config[device].getboolean('iptables'):
                dev_app_uid = self.config[device][app+'_uid']
                chain = self.config['iptables']['chain']
                subprocess.check_call('adb -s {0} shell su -c "iptables -D {1} -m owner --uid-owner {2} -j RETURN"'.format(device, chain, dev_app_uid),
                                      shell=True)
        time.sleep(1)
