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
'''

import subprocess
import os
import time
import sys
import signal
import configparser

class MyException(Exception):
    '''
    Exception to raise if something bad happened.
    '''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

#Handler for the SIGHUP signal
def close(sig, frame):
    '''
    signal handler that listens to SIGHUP and SIGINT and therminates the network if necessary.
    '''
    for command in running_commands:
        os.killpg(command.pid, signal.SIGTERM)
    sys.exit()



def set_up(host):
    '''
    Establishes the tunnel and checks regulary if it is still running
    '''

    direc = os.path.dirname(__file__)
    config = configparser.ConfigParser()
    if direc == '':
        config.read('network.ini')
    else:
        config.read(direc+'/network.ini')

    global running_commands
    running_commands = []
    steps = int(config['general']['steps'])

    '''
    The network script can start multiple commands listed in the config file
    Each command can request the host name as parameter.
    If it ends, the script waits activly till it returns,
    if not, the script starts the execution, waits a timeout
    and checks regularly if the command is still running afterwards.
    '''
    
    try:
        i = 1
        while i <= steps:
            parameters = config['step'+str(i)]['parameter'].split(', ')
            command = config['step'+str(i)]['command']
            for parameter in parameters:
                if parameter == 'host':
                    command = command + host

            timeout = int(config['step'+str(i)]['timeout'])
            if config['step'+str(i)].getboolean('ends'):
                subprocess.check_call(command, shell=True)
            else:
                run_command = subprocess.Popen(command,
                                               shell=True,
                                               preexec_fn=os.setsid)
                running_commands = running_commands + [run_command]
            time.sleep(timeout)
            i = i+1

        while True:
            for command in running_commands:
                if command.poll() is not None:
                    '''
                    If the tunnel isn't running anymore terminate tcpdump
                    and raise an exception with the error message
                    '''
                    for rest in running_commands:
                        if rest is not command:
                            os.killpg(rest.pid, signal.SIGTERM)
                output, error = command.communicate()
                print(error)
                raise MyException(error)
            time.sleep(2)

    except Exception as error:
        '''
        The exception gets catched to print the message
        and stop the execution of the whole programm with an execution status different from 0
        '''
        for command in running_commands:
            if command.poll() is None:
                os.killpg(command.pid, signal.SIGTERM)
        print(error)
        sys.exit(3)


def main():
    '''
    the network setup needs a hostname to connect to.
    '''
    if len(sys.argv) < 2:
        #Test if the programm gets executed with to less parameters
        print('The programme needs a hostname to run')
        sys.exit(1)
    '''
    Get the hostname and start the programm
    The main purpose of this programm is to be started over a SSH connection in a pseudo-terminal.
    If the SSH channel gets closed all started processes receive the SIGHUP signal.
    We use it to finally teminate all executed subprocesses 
    '''
    signal.signal(signal.SIGHUP, close)
    signal.signal(signal.SIGINT, close)
    host = sys.argv[1]
    set_up(host)

if __name__ == '__main__':
    main()
