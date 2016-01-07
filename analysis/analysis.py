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

The script analysies a .dump file:
It runs with scapy through the file and stores all DNS results in files.
Afterwards it starts path measurements from a remote node to the targets of all network connections.
The path measuremetns can get executed in application and in parallel.
Before executing the path measurements a filter with IPs or Ports can get applied
'''
import ConfigParser
import subprocess
import os
import scapy
from scapy.all import *
from scapy.layers import *
import time

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

def analyze(directory, capture, country, hostname, application, counter):
    '''
    Funtion, analysing the .dump file.
    '''
    direc = os.path.dirname(__file__)
    if direc != '':
        direc = direc + '/'
    config = ConfigParser.ConfigParser()
    config.read(direc+'analysis.ini')

    method = config.get('general', 'method', 0)
    options = config.get('general', 'options', 0)
    '''
    If a network commection was established from the Internet to the devices in the framework,
    the path measurement has to be made to the source address and source port.
    Therefore the script needs to know the IP of the framework device.
    '''
    ipaddress = config.get('general', 'ip_address', 0)
    identifier = config.get('general', 'identifier', 0)
    ip_blacklist = config.get('general', 'ip_blacklist', 0).split(', ')
    port_blacklist = config.get('general', 'port_blacklist', 0).split(', ')
    username = config.get('general', 'username', 0)
    pkey = config.get('general', 'pkey', 0)
    

    if 'True' == config.get('general', 'parallel', 0):
        parallel = True
    else:
        parallel = False
    if 'True' == config.get('general', 'in_application', 0):
        inapplication = True
    else:
        inapplication = False
    if inapplication:
        port_option = config.get('in_application', 'port_option', 0)
        tcp_option = config.get('in_application', 'tcp_option', 0)
        udp_option = config.get('in_application', 'udp_option', 0)

    #Opens the .dump file with scapy
    packets = sniff(offline=directory+capture)

    dns_host_list_of_answer = []
    prot_ip_port = []

    for p in packets:
        '''
        To make in application path measurement, a triple for each network connection is necessary:
        1. used protocol: TCP or UDP
        2. IP address
        3. Port number
        '''
        if p.haslayer(UDP):
            if p.haslayer(DNS):
                '''
                DNS resolutions are not considered for the path measurements.
                The DNS responses are directly stored in extra files.
                The requested hostname is the filename and the resulting IPs the content of the file
                '''
                if p[DNS].qr == 1:
                    i = 0
                    f = open(directory + counter + '_' + identifier + '_' + application + '_' +
                             country + '_' + hostname + '_DNS_' + p[DNS].qd.qname, 'a')
                    while i < p[DNS].ancount:
                        f.write(str(p[DNS].an[i].rdata)+'\n')
                        i = i+1
                    f.close()
            else:
                #The IP address of the framework device is no target for path measurements
                if p[IP].src == ipaddress:
                    #Only differing triples are stored
                    if p[IP].dst not in ip_blacklist and str(p[UDP].dport) not in port_blacklist:
                        help = ('UDP', p[IP].dst, p[UDP].dport)
                        if help not in prot_ip_port:
                            print(help)
                            prot_ip_port = prot_ip_port +[help]
                else:
                    #Only differing triples are stored
                    if p[IP].src not in ip_blacklist and str(p[UDP].sport) not in port_blacklist:
                        help = ('UDP', p[IP].src, p[UDP].sport)
                        if help not in prot_ip_port:
                            print(help)
                            prot_ip_port = prot_ip_port +[help]
        elif p.haslayer(TCP):
            #The same for TCP as for UDP
            if p[IP].src == ipaddress:
                if p[IP].dst not in ip_blacklist and p[TCP].dport not in port_blacklist:
                    help = ('TCP', p[IP].dst, p[TCP].dport)
                    if help not in prot_ip_port:
                        prot_ip_port = prot_ip_port +[help]
            else:
                if p[IP].src not in ip_blacklist and p[TCP].sport not in port_blacklist:
                    help = ('TCP', p[IP].src, p[TCP].sport)
                    if help not in prot_ip_port:
                        prot_ip_port = prot_ip_port +[help]

    traces = []
    filenames = []
    '''
    Command is the path measurement that is executed on a remote node:
    For example:
    echo "sudo traceroute -U -p 23 1.2.3.4; exit" | ssh -i ~/.ssh/rsa_key user@hostname

    echo "sudo traceroute -T -p 443 1.2.3.4; exit" | ssh -tt -i ~/.ssh/rsa_key user@hostname

    TCP traceroutes require root rights. Some SSH configurations don't allow
    fowarding commands as root wothout a Shell.
    '-tt' requests a pseudo terminal.
    Tests showed only even numbers of '-t' works.

    Filename is the file were to store the result of the path measurement with the directory.
    For example:
    /home/result/whatsapp/0001_2_whatsapp_DE_example.tum.de_traceroute_to_1.2.3.4_port_443
               _proto_TCP_at_01.02.3456_16:25:12.txt
    '''

    if parallel:
        '''
        If the path measurements can be executed in parallel, they are started with subprocess.Popen
        and the handler 'process' is stored in a list and the according filename in another.
        Sometimes plenty of path measurements have to be executed in parallel, to not open to many
        SSH connections in to short time, a 1s timeout is waited before each.
        At the end, the function waits for every process to terminate
        and stores the output in the according file.
        '''
        for alt in prot_ip_port:
            timestamp = get_date() + '_' + get_time()
            if inapplication:
                if alt[0] == 'UDP':
                    #Concatenating the command
                    command = 'echo "sudo ' + method + ' ' + udp_option + ' ' + port_option + ' '
                    command = command + str(alt[2])+ ' ' + str(alt[1]) + ' ; exit" | ssh -i '
                    command = command + pkey + ' ' +username + '@' + hostname
                    time.sleep(1)
                    #exectuing the command
                    process = subprocess.Popen(command,
                                               shell=True,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
                    #concatenating the filename
                    filename = '_traceroute_to_'+str(alt[1])+'_port_' + str(alt[2])+'_proto_UDP_at_'
                    filename = filename +timestamp+'.txt'
                    #adding the handler and the filename to the according list
                    traces = traces + [process]
                    filenames = filenames + [filename]

                else:
                    #Concatenating the command
                    command = 'echo "sudo ' + method + ' ' + tcp_option + ' ' + port_option + ' '
                    command = command + str(alt[2])+ ' ' + str(alt[1]) + ' ; exit" | ssh -tt -i '
                    command = command + pkey + ' ' +username+'@'+hostname
                    time.sleep(1)
                    #exectuing the command
                    process = subprocess.Popen(command,
                                               shell=True,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
                    #concatenating the filename
                    filename = '_traceroute_to_'+str(alt[1])+'_port_' + str(alt[2])+'_proto_TCP_at_'
                    filename = filename + timestamp+'.txt'
                    #adding the handler and the filename to the according list
                    traces = traces + [process]
                    filenames = filenames + [filename]
            else:
                #Concatenating the command
                command = 'echo "sudo ' + method + ' ' + str(alt[1]) + ' ; exit" | ssh -i ' + pkey
                command = command + ' ' +username+'@'+hostname
                time.sleep(1)
                #exectuing the command
                process = subprocess.Popen(command,
                                           shell=True,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
                #concatenating the filename
                filename = '_traceroute_to_'+str(alt[1])+ '_at_'+timestamp+'.txt'
                #adding the handler and the filename to the according list
                traces = traces + [process]
                filenames = filenames + [filename]

        for trace in traces:
            '''
            Waiting actively for each process to finish.
            Writing the results to files afterwards.
            '''
            out, err = trace.communicate()
            filename = directory + counter + '_' + identifier + '_' + application + '_' + country
            filename = filename +  '_' + hostname + filenames.pop(0)
            f = open(filename, 'w')
            f.write(out)
            f.close()

    else:
        '''
        If the path measurements can not be executed parallel, they are started with
        subprocess.check_output.
        This time, the function waits actively for every output and stores it directly in
        the according file.
        '''
        for alt in prot_ip_port:
            timestamp = get_date() + '_' + get_time()
            if inapplication:
                if alt[0] == 'UDP':
                    #Concatenating the command
                    command = 'echo "sudo  ' + method + ' ' + udp_option + ' ' + port_option + ' '
                    command = command + str(alt[2])+ ' ' + str(alt[1]) + ' ; exit" | ssh -i '
                    command = command + pkey + ' ' +username+'@'+hostname
                    #exectuing the command
                    out = subprocess.check_output(command, shell=True)
                    #concatenating the filename
                    filename = directory + counter + '_' + identifier + '_' + application + '_'
                    filename = filename + country + '_' + hostname +'_to_'+str(alt[1])+'_port_'
                    filename = filename + str(alt[2]) + '_proto_UDP_at_' + timestamp + '.txt'
                    #writing the results in a file
                    f = open(filename, 'w')
                    f.write(out)
                    f.close()
                else:
                    #Concatenating the command
                    command = 'echo "sudo ' + method + ' ' + tcp_option + ' ' + port_option + ' '
                    command = command + str(alt[2]) + ' ' + str(alt[1]) + ' ; exit" | ssh -tt  -i '
                    command = command + pkey + ' ' + username + '@' + hostname
                    #exectuing the command
                    out = subprocess.check_output(command, shell=True)
                    #concatenating the filename
                    filename = directory +counter + '_' + identifier + '_' + application + '_'
                    filename = filename + country + '_' + hostname + '_to_'+str(alt[1])+'_port_'
                    filename = filename + str(alt[2]) + '_proto_TCP_at_' + timestamp + '.txt'
                    #writing the results in a file
                    f = open(filename, 'w')
                    f.write(out)
                    f.close()
            else:
                #Concatenating the command
                command = 'echo "sudo ' + method + ' ' + str(alt[1]) + ' ; exit" | ssh -i '
                command = command + pkey + ' ' +username+'@'+hostname
                #exectuing the command
                out = subprocess.check_output(command, shell=True)
                #concatenating the filename
                filename = directory +counter + '_' + identifier + '_' + application + '_' + country
                filename = filename + '_'+hostname + '_to_' + str(alt[1]) +'_at_'+ timestamp +'.txt'
                #writing the results in a file
                f = open(filename, 'w')
                f.write(out)
                f.close()

def main():
    '''
    The script needs 6 parameters:
    1. A directory where the .dump file is located and where to store the results afterwards.
    2. The name of the .dump file.
    3. The country code of the remote node
    4. The hostname of the remote node
    5. The name of the measured smartphone application
    6. The actual counter to store the results unique
    '''
    if len(sys.argv) < 7:
        #Test if the programm gets executed with to less parameters
        print('''
              The script needs 6 parameters:
              1. A directory where the .dump file is located and where to store the results afterwards.
              2. The name of the .dump file.
              3. The country code of the remote node
              4. The hostname of the remote node
              5. The name of the measured smartphone application
              6. The actual counter to store the results unique
              ''')
        sys.exit(1)
    directory = sys.argv[1]
    capture = sys.argv[2]
    country = sys.argv[3]
    hostname = sys.argv[4]
    application = sys.argv[5]
    counter = sys.argv[6]
    analyze(directory, capture, country, hostname, application, counter)

if __name__ == '__main__':
    main()
