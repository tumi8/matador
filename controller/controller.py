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

import sys
import subprocess
import signal
import paramiko
import configparser
import os
import time

class Host1Exception(Exception):
    '''
    Exception if the network component on router 1 fails
    '''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Host2Exception(Exception):
    '''
    Exception if the network component on router 2 fails
    '''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class FatalException(Exception):
    '''
    Exception if a fatal error occured and the controller will not
    work in a next step again
    '''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class SmallException(Exception):
    '''
    Exception if a small error occured
    this experiment has to be interrupted but the controller can
    work in a next step again
    '''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def get_time():
    '''
    returns the time
    '''
    localtime = time.localtime()
    return str(localtime[3]) + ':' + str(localtime[4]) + ':' + str(localtime[5])

def get_date():
    '''
    returns the date
    '''
    localtime = time.localtime()
    if localtime[1] < 10:
        month = '0'+str(localtime[1])
    else:
        month = str(localtime[1])
    return str(localtime[0]) + '_' + month + '_' + str(localtime[2])


def clean_up(commands, channels):
    '''
    kills all processes in the commands list
    closes all ssh channels in the channels list
    '''
    for command in commands:
        if command.poll() is None:
            os.killpg(command.pid, signal.SIGINT)
    for chan in channels:
        if not chan.exit_status_ready():
            chan.close()


def force_stop(config, ssh_worker):
    '''
    Sometimes the network components did not close propery,
    this function calls scripts that check the correct tear down and force it if necessary
    '''
    command = config['network_tear_down_1']['command']
    try:
        subprocess.check_call(command,
                              shell=True)
    except:
        raise FatalException('Can not tear down the tunnel')

    command = config['network_tear_down_2']['command']
    try:
        ssh_worker.exec_command(command)
    except:
        raise FatalException('Can not tear down the tunnel')

def experiment(countries, hostnames, coordinates, counter, storage_directory):
    '''
    An experiment executes all necessary steps.
    1. network setup
    2. location setup
    3. measurement setup
    4. app execution
    5. data analysis
    6. result backup
    7. clean up
    '''
    direc = os.path.dirname(__file__)
    if direc != '':
        direc = direc + '/'

    config = configparser.ConfigParser()
    config.read(direc + 'controller.ini')

    '''
    The second router of the setup is controlled over SSH.
    All necessary parameters are in the controller.ini file.
    Pramiko is used for the ssh connection to the second router.
    '''
    worker = config['general']['worker']
    private_key = paramiko.RSAKey.from_private_key_file(config[worker]['pkey'])
    username = config[worker]['username']
    ipaddress = config[worker]['ip']
    ssh_worker = paramiko.SSHClient()
    ssh_worker.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_worker.connect(ipaddress, username=username, password='', pkey=private_key)
    time.sleep(2)


    '''
    The network setup is done localy with a subprocess.
    '''
    command = config['network_setup_1']['command'] + ' ' + hostnames[0]
    setup_network_1 = subprocess.Popen(command,
                                       shell=True,
                                       stderr=subprocess.PIPE,
                                       preexec_fn=os.setsid)

    '''
    The network setup on the second router is made on over SSH.
    A new Paramiko session is opend and the get_pty() method used
    to get a tty.
    Whenever the connection to the second router gets interrupted or closed,
    all process sartet in the tty session receive a SIGHUP signal.
    '''
    command = config['network_setup_2']['command'] + ' ' + hostnames[1]
    setup_network_2 = ssh_worker.get_transport().open_session()
    setup_network_2.get_pty()
    setup_network_2.exec_command(command)

    '''
    The Xprivacy settings get changed on the smartphones.
    The process gets filmed addtionally.
    1. Create Filenames
    2. start Xprivacy change script with the coodinates and the filenames
    '''
    video_file1 = storage_directory + 'xprivacy/' + counter+'_1_' + countries[0] + '_'
    video_file1 = video_file1 + hostnames[0] + '_to_'+ countries[1] + '_' + hostnames[1] + '.mp4'

    video_file2 = storage_directory + 'xprivacy/' + counter + '_2_' + countries[0] + '_'
    video_file2 = video_file2 + hostnames[0] + '_to_'+ countries[1] + '_' + hostnames[1] + '.mp4'

    command = config['location_setup']['command'] + ' ' + coordinates[0] + ' ' + coordinates[1]
    command = command + ' ' + video_file1 + ' ' + video_file2

    try:
        subprocess.check_call(command, shell=True)
    except:
        raise FatalException('The smartphones are not working')

    #To make sure, the tunnels are established even to slower nodes, a timeout is waited.
    time.sleep(100)

    '''
    Afterwards the network check script get executed on both routers
    and Exceptions raised if necessary.
    '''
    command = config['network_check_1']['command']
    try:
        subprocess.check_call(command, shell=True)
    except Exception as error:
        print(error)
        clean_up([], [setup_network_2])
        force_stop(config, ssh_worker)
        raise Host1Exception('Host1 does not work')

    command = config['network_check_2']['command']
    check_2 = ssh_worker.get_transport().open_session()
    check_2.get_pty()
    check_2.exec_command(command)
    if check_2.recv_exit_status() != 0:
        clean_up([setup_network_1], [])
        force_stop(config, ssh_worker)
        raise Host2Exception('Host2 does not work')

    '''
    The following loop gets executed for each application measured and listed in this .ini file
    '''
    applications = config['general']['applications'].split(', ')
    for app in applications:
        #Check if the tunnels are still working
        if setup_network_1.poll() is not None:
            print('test2')
            clean_up([], [setup_network_2])
            force_stop(config, ssh_worker)
            raise Host1Exception('Host1 does not work')
        elif setup_network_2.exit_status_ready():
            print('test3')
            clean_up([setup_network_1], [])
            force_stop(config, ssh_worker)
            raise Host2Exception('Host2 does not work')

        '''
        Starting the interception routine on both routers.
        '''
        timestamp = get_date()+'_'+get_time()

        result_1 = counter + '_1_' + app + '_' +countries[0] + '_' + hostnames[0] +'_tcpdump_to_'
        result_1 = result_1 + countries[1] + '_' + hostnames[1] + '_' + timestamp+'.dump'

        result_2 = counter + '_2_' + app + '_' +countries[1] + '_' + hostnames[1] +'_tcpdump_to_'
        result_2 = result_2 + countries[0] + '_' + hostnames[0] + '_' + timestamp+'.dump'

        command = config['measurement_setup_1']['command'] + ' '+ storage_directory + app + '/'
        command = command + result_1
        setup_measurement_1 = subprocess.Popen(command,
                                               shell=True,
                                               stderr=subprocess.PIPE,
                                               preexec_fn=os.setsid)

        command = config['measurement_setup_2']['command'] + ' ' + storage_directory + app + '/'
        command = command + result_2
        setup_measurement_2 = ssh_worker.get_transport().open_session()
        setup_measurement_2.get_pty()
        setup_measurement_2.exec_command(command)

        time.sleep(2)

        #Check if both are running
        if setup_measurement_1.poll() is not None:
            print('test4')
            clean_up([setup_network_1], [setup_network_2, setup_measurement_2])
            force_stop(config, ssh_worker)
            raise Host1Exception('tcpdump problem on host 1 in step '+ counter)
        elif setup_measurement_2.exit_status_ready():
            print('test5')
            clean_up([setup_measurement_1, setup_network_1], [setup_network_2])
            force_stop(config, ssh_worker)
            raise SmallException('tcpdump problem on host 1 in step '+ counter)

        '''
        The application execution is recorded again.
        New filenames are created.
        Application execution with the parameters
        1. app
        2. video file name 1
        3. video file name 2
        '''
        video_file1 = storage_directory + app + '/' + counter + '_1_' + app + '_' + countries[0]
        video_file1 = video_file1 + '_' + hostnames[0] + '.mp4'
        video_file2 = storage_directory + app + '/' + counter + '_2_' + app + '_' + countries[1]
        video_file2 = video_file2 + '_' + hostnames[1] + '.mp4'
        video = video_file1 + ' ' + video_file2

        command = config['app_execution']['command'] + ' ' + app + ' ' +  video
        try:
            subprocess.check_call(command, shell=True)
        except Exception as error:
            '''
            If the application execution raises an Exception,
            the smartphones have to be cleaned up
            and the measurement and network components het termianted.
            '''
            try:
                command = config['app_execution']['clean_up']
                subprocess.check_call(command, shell=True)
            except Exception as error:
                '''
                If the clean up failes the controller terminates and raises a Fatal exception
                '''
                clean_up([setup_network_1, setup_measurement_1],
                         [setup_network_2, setup_measurement_2])
                force_stop(config, ssh_worker)
                raise FatalException('The smarphones completely do not work')
            clean_up([setup_network_1, setup_measurement_1],
                     [setup_network_2, setup_measurement_2])
            force_stop(config, ssh_worker)
            raise SmallException('The smartphones do not work: ' + str(error))

        '''
        After the application execution, both interception programms get terminated
        and the analysis scripts on both routers started.
        '''
        clean_up([setup_measurement_1], [setup_measurement_2])

        command = config['analysis_1']['command'] + ' ' +storage_directory  + app + '/' + ' '
        command = command + result_1 + ' ' + countries[0]+ ' ' +hostnames[0] + ' ' + app + ' '
        command = command + counter

        analysis_1 = subprocess.Popen(command,
                                      shell=True,
                                      stderr=subprocess.PIPE,
                                      preexec_fn=os.setsid)

        command = config['analysis_2']['command']+ ' ' + storage_directory + app + '/' +  ' '
        command = command + result_2 + ' ' + countries[1] + ' ' +hostnames[1] + ' ' + app + ' '
        command = command + counter
        analysis_2 = ssh_worker.get_transport().open_session()
        analysis_2.get_pty()
        analysis_2.exec_command(command)

        analysis_1.communicate()
        if analysis_1.poll() != 0:
            clean_up([setup_network_1], [setup_network_2])
            force_stop(config, ssh_worker)
            raise SmallException('The analysis of step '+ counter+ ' failed.')

        if analysis_2.recv_exit_status() != 0:
            clean_up([setup_network_1], [setup_network_2])
            force_stop(config, ssh_worker)
            raise SmallException('The analysis of step '+ counter+ ' failed.')

    '''
    The results get copied to a more reliable storage server.
    '''
    command = config['save_1']['command']
    try:
        subprocess.check_call(command, shell=True)
    except:
        clean_up([setup_network_1], [setup_network_2])
        force_stop(config, ssh_worker)
        raise SmallException('Mob2 could not copy to the server on step ' + counter)

    command = config['save_2']['command']
    try:
        ssh_worker.exec_command(command)
    except:
        clean_up([setup_network_1], [setup_network_2])
        force_stop(config, ssh_worker)
        raise SmallException('Mob1 could not copy to the server on step ' + counter)

    '''
    At the end, the network setup gets closed.
    '''
    clean_up([setup_network_1], [setup_network_2])
    force_stop(config, ssh_worker)

def main():

    '''
    The controller is called with 8 arguments:
    1. The country code for the first tunnel
    2. The hostname for the first tunnel
    3. The coordinates, according to the first tunnel endpoint
    4. The country code for the second tunnel
    5. The hostname for the second tunnel
    6. The coordinates, according to the second tunnel endpoint
    7. A counter to save the results unique
    8. A directory were to save the results on both routers
    The method experiment is called wit all arguments
    '''

    if len(sys.argv) < 9:
        #Test if the programm gets executed with to less parameters
        print('The programme needs two hostnames')
        sys.exit(1)


    countries = [sys.argv[1], sys.argv[4]]
    hostnames = [sys.argv[2], sys.argv[5]]
    coordinates = [sys.argv[3], sys.argv[6]]
    counter = sys.argv[7]
    directory = sys.argv[8]
    experiment(countries, hostnames, coordinates, counter, directory)

if __name__ == '__main__':
    main()
