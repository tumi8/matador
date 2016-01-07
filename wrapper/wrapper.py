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

A wrapper that need a country list with hostnames as input,
builds pairs out of them and starts the controller.

Input File: sorted list of Hostnames with informations
    Elements: (CountryCode Hostname Longitude Latitude)
    SortKey: CountryCode
    For example:
        BE planetlab1.extern.kuleuven.be 50.8625 4.68599
        CH planetlab2.inf.ethz.ch 47.3794 8.54513
        CZ planetlab1.cesnet.cz 50.102 14.3916

    Pairs:
        BE <-> BE
        BE <-> CH
        BE <-> CZ
        CH <-> CH
        ...
'''
import configparser
import subprocess
import controller
import time
import sys
import os

def write_log(file, text):
    '''
    writes a log message with a timestamp to the according log file.
    '''
    file = open(file, 'a')
    timestamp = get_date() + ' ' + get_time()
    file.write(timestamp + ': ' + text + '\n')
    file.close()

def get_time():
    '''
    returns the time
    '''
    ltime = time.localtime()
    return str(ltime[3]).zfill(2) + ':' + str(ltime[4]).zfill(2) + ':' + str(ltime[5]).zfill(2)

def get_date():
    '''
    returns the date
    '''
    ltime = time.localtime()
    return str(ltime[0]).zfill(2) + '_' + str(ltime[1]).zfill(2) + '_' + str(ltime[2]).zfill(2)

def execute():
    '''
    The Config file holds the input file name
    Input File: sorted list of Hostnames with informations
        Elements: (CountryCode Hostname Longitude Latitude)
        SortKey: CountryCode
    '''
    direc = os.path.dirname(__file__)
    if direc != '':
        direc = direc + '/'

    config = configparser.ConfigParser()
    config.read(direc + 'wrapper.ini')

    '''
    A directory path were to store the results is given in the log file
    '''

    storage_directory = config['general']['storage_directory']

    '''
    There should be a name for a log file to use in the config file.
    Otherwise a default value (default_log) is used.
    '''

    logfile = config['general']['log_file']
    if logfile == '':
        logfile = 'default_log'

    write_log(logfile, 'Starting the measurement')
    #initialization
    steps = int(config['initialization']['steps'])
    i = 1
    while i <= steps:
        try:
            command = config['initialization_step'+str(i)]['command']
            timeout = int(config['initialization_step'+str(i)]['timeout'])
            subprocess.check_call(command, shell=True)
            time.sleep(timeout)
            i = i+1
        except Exception as error:
            write_log(logfile, 'The initialization failed with: ' + str(error))
            sys.exit(1)

    '''
    The Input file is reead and the values are saved in a list:
    country_list = [[country_code, [hostname, longitude, latitude]*]*]
    '''
    file = open(config['general']['input_file'])
    country_list = []
    country = []
    country_code = ' '

    #each line gets inspected seperatly
    for line in file:
        helper = line.split()
        #if the country code stays the same the hostname and coordinates get added to this country
        if country_code == helper[0]:
            country = country + [helper[1:4]]
        #if the country code changes, the country gets added to the country list
        #and a new country starts
        else:
            country_list = country_list + [country]
            country_code = helper[0]
            country = [helper[0], helper[1:4]]
    '''
    The above algorithm starts with an empty list at the beginning
    that has to be removed from the list
    '''
    country_list = country_list[1:] + [country]

    #To run through all countries we need the number of different countires
    dif_countries = len(country_list)

    '''
    The experiment needs pairs of hostnames for each country pair.
    To control if a pair of countries was already used succesfully a matrix is used
    The matriy gets populated with the following values:
        1: the country pair was never used yet
        2: the country pair was used in an experiemnt
           but the hostname of one country didn' worked in another experiment.
        3: the country pair was used in an experiment
        0: the country pair wasn't used yet and one of the countires has no more hostname to use
        4: A small error happend during the execution
           the country pair needs to be measured again seperately
    '''
    matrix = [[1 for x in range(dif_countries)] for x in range(dif_countries)]
    counter = 0

    write_log(logfile, 'Successfull initialization')

    '''
    Iterate through all possible country pairs.
    Because of the fluctuation in the planet lab uptimes n iterations are done.
    The number of iterations can be changed in the ini file.
    '''

    i = 0
    while i < dif_countries:
        if len(country_list[i]) > 1:
            j = 0
            country1 = country_list[i][0]
            hostname1 = country_list[i][1][0]
            longitude1 = country_list[i][1][1]
            latitude1 = country_list[i][1][2]
            while j < dif_countries:
                if len(country_list[j]) > 1:
                    country2 = country_list[j][0]
                    hostname2 = country_list[j][1][0]
                    longitude2 = country_list[j][1][1]
                    latitude2 = country_list[j][1][2]

                    '''
                    Because of the implementation
                    it can happen that a matrix field can be visited twice or more.
                    The experiment was already done for a value greater then 2
                    or is not possible anymore for a value smaller then 1
                    '''
                    if 0 < matrix[i][j] <= 2:
                        try:
                            '''
                            Ideally the experiment works:
                            j gets incremented to get the next country
                            the counter gets incremented to have a new unique number
                            to store the results
                            the two fields in the matrix representig the country pair are set to 3
                            '''
                            message = 'Start experiment '+ str(counter) +' between '
                            message = message + hostname1 + ' and ' + hostname2
                            write_log(logfile, message)
                            controller.experiment([country1, country2],
                                                  [hostname1, hostname2],
                                                  [longitude1+','+latitude1,
                                                   longitude2+','+latitude2],
                                                  str(counter).zfill(4),
                                                  storage_directory)
                            matrix[i][j] = 3
                            matrix[j][i] = 3
                            counter = counter + 1
                            j = j+1
                            write_log(logfile, 'The experiment was successful')

                        except controller.Host1Exception as error:
                            '''
                            When the experiment ends with an exception,
                            because Host1 didn't worked correctly ,
                            the hostname gets poped out of the list.
                            All pairs containing the country of this hostname
                            are set back from 3 to 2
                            because we want all experiments
                            for one server executed from one hostname.
                            '''
                            message = 'ERROR: ' + hostname1
                            message = message + ' did not work properly. ' + str(error)
                            message = message + ' The next hostname of this country will be tried'
                            write_log(logfile, message)
                            country_list[i].pop(1)
                            k = 0
                            while k < dif_countries:
                                if matrix[k][i] == 3:
                                    matrix[k][i] = 2
                                if matrix[i][k] == 3:
                                    matrix[i][k] = 2
                                k = k+1
                            i = i-1
                            j = 0
                            break

                        except controller.Host2Exception as error:
                            '''
                            When the experiment ends with an exception,
                            because Host2 didn't worked correctly,
                            the hostname gets poped out of the list.
                            All pairs containing the country of this hostname
                            are set back from 3 to 2
                            because we want all experiments for one server executed
                            from one hostname.
                            The inner while loop is exited to start with this country again.
                            '''
                            message = 'ERROR: ' + hostname2
                            message = message + ' did not work properly. ' + str(error)
                            message = message + ' The next hostname of this country will be tried'
                            write_log(logfile, message)
                            country_list[j].pop(1)
                            k = 0
                            while k < dif_countries:
                                if matrix[k][j] == 3:
                                    matrix[k][j] = 2
                                if matrix[j][k] == 3:
                                    matrix[j][k] = 2
                                k = k+1
                            if i > j:
                                i = j-1
                            j = 0
                            break

                        except controller.FatalException as error:
                            '''
                            Fatal Exceptions occurs
                            for example when the smartphones don't work correctly.
                            Then everything needs to get stopped.
                            '''
                            message = 'ERROR: A fatal exception has occured: ' + str(error)
                            message = message + '\n The measurement was terminated'
                            write_log(logfile, message)
                            sys.exit(3)

                        except controller.SmallException as error:
                            matrix[i][j] = 4
                            matrix[j][i] = 4
                            counter = counter + 1
                            j = j+1
                            '''
                            SmallExceptions occurs
                            for example when the files couldn't get stored on the server.
                            Only a warning shoud be printed but nothing bad happend.
                            '''
                            message = 'WARNING: A small exception has occured: ' + str(error)
                            message = message + '\n The measurement goes on with the next step'
                            write_log(logfile, message)

                    else:
                        j = j+1

                else:
                    '''
                    When all possible hostnames of a country failed,
                    a warning is written
                    and every value 1 in the matrix containing this country is set to 0
                    '''
                    message = 'Tried '+ str(country_list[i][0])+ ' with ' + str(country_list[j][0])
                    message = message + '\n ERROR: All Nodes of the country '
                    message = message + str(country_list[j][0]) + ' did not work'
                    write_log(logfile, message)
                    k = 0
                    while k < dif_countries:
                        if matrix[k][j] == 1:
                            matrix[k][j] = 0
                        if matrix[j][k] == 1:
                            matrix[j][k] = 0
                        k = k+1
                    j = j+1
        else:
            '''
            When all possible hostnames of a country failed,
            a warning is written
            and every value 1 in the matrix containing this country is set to 0
            '''
            message = 'Tried to combine '+ str(country_list[i][0])
            message = message + ' with other countries \n ERROR: All Nodes of the country '
            message = message + str(country_list[i][0])+ ' did not work'
            write_log(logfile, message)
            k = 0
            while k < dif_countries:
                if matrix[k][i] == 1:
                    matrix[k][i] = 0
                if matrix[i][k] == 1:
                    matrix[i][k] = 0
                k = k+1

        i = i+1

    write_log(logfile, 'All possible pairs were tried and  they were neither successfull or failed')

    '''
    If there are some steps listed in the config file to complete the measurement,
    they are executed as process calls
    '''

    steps = int(config['completion']['steps'])
    i = 1
    while i <= steps:
        command = config['completion_step'+str(i)]['command']
        timeout = int(config['completion_step'+str(i)]['timeout'])
        subprocess.check_call(command, shell=True)
        time.sleep(timeout)
        i = i+1

    write_log(logfile, 'The Completion was successfull and the measurement ends: ')

    result = '\n   '

    for country in country_list:
        result = result + country[0]+' '
    result = result + '\n'

    i = 0
    while i < dif_countries:
        result = result + country_list[i][0] + ' '
        for value in matrix[i]:
            result = result + str(value).zfill(2) + ' '
        result = result + '\n'
        i = i+1

    write_log(logfile, result)

def main():
    '''
    Only calls the execute function
    '''
    if len(sys.argv) < 1:
        #Test if the programm gets executed with to less parameters
        print('The programme needsnothing')
        sys.exit(1)

    execute()

if __name__ == '__main__':
    main()
