MATAdOR
Index
-----

* [Description](#description)
* [Features](#features)
* [Design](#design)
* [Requirements](#requirements)
* [Dependencies](#dependencies)
* [Bundled Sources](#bundled-sources)
* [Structure](#structure)
    * [Wrapper Modules](#wrapper-modules)
    * [Controller Module](#controller-module)
    * [Network Modules](#network-modules)
    * [Mobile Phone Modules](#mobile-phone-modules)
    * [Analysis Module](#analysis-module)
* [Exemplary Setup](#examplary-setup)
    * [Routers](#routers)
    * [Tunnel Netwok Namespaces](#tunnel-network-namespaces)
    * [Controller](#controller)
    * [Android Mobile Phones](#android-mobile-phones)
    * [Framework Configurations](#framework-configurations)

Description
-----------

MATAdOR is an extensible, transparent and automated framework to analyze communication behaviors of mobile messaging applications.
It is exchanges mobile messages between Android mobile phones and emulates geographical distributed
senders and receivers by tunneling the complete network traffic through remote nodes.
The coordinates of the mobile phones get changed accordingly to make sure the mobile phones do not change their behavior.
The framework automates the network tunneling and the message sending on the mobile phones.
It intercepts the complete network traffic originating from the mobile phones for further analysis.

This README gives an overview about the framework and its functionalities. Furthermore it describes the exemplary setup with configuration files and explanations. For further information about the implementation please refer to the docstrings in the python modules and refer to the Bachelor Thesis "Security Analysis of Mobile Messaging Traffic with an Automated Test Framework" from Johannes Zirngibl. The Bachelor thesis describes the framework in more detail and shows a first use case.

Features
--------

* Mobile phone applications are executed natively on Android mobile phones
* Supported mobile messaging applications by now:
    * WhatsApp
    * Wechat
    * Threema
    * Textsecure
* The network traffic is tunneled transparently for the mobile phones
* The mobile phone location gets changed
* The complete network traffic is intercepted
* The execution is completely automated
* Analysis steps are integrated (e.g. path measurements)
* Traffic can be firewalled

Design
-----------

The illustration shows the design of the framework. The mobile messaging applications are installed and executed
on Android mobile phones. They are integrated into the framework to tunnel the traffic transparently
and to control and automate the message exchange. Two routers span wireless networks the mobile phones have to connect
to. The complete network traffic is tunneled from the two routers through remote proxy nodes.
The routers are further used to intercept the network traffic and execute first analysis steps.
A controller establishes the network tunnels and network connections and automates the message sending on the mobile phones.
The controller has to be connected to both routers and the mobile phones.

<img src="illustrations/overall.png?raw=true" width="600" height="450" hspace="4"/>

Requirements
-----------
* 2 GNU/Linux routers
    * Wireless Access points 
    * DHCP server (e.g. isc-dhcp-server: https://www.isc.org/downloads/dhcp/)
    * path measurement tool (e.g. traceroute: http://linux.die.net/man/8/traceroute)
    * network traffic interception tool (e.g. tcpdump. http://www.tcpdump.org/tcpdump_man.html)
* 2 Android mobile phones  
    * root
    * activated Android Debugging Mode
    * iptables (optional)
    * XPrivacy (optional, https://github.com/M66B/XPrivacy#xprivacy)
* Access to a distributed Testbed (e.g PlanetLab: http://planet-lab.org/)
    * SSH access
    * Possibility to create raw sockets
    

Dependencies
-----------
* Python 3 and 2.7 (https://www.python.org/)
* Android Debug Bridge (http://developer.android.com/tools/help/adb.html)
* Scapy (http://www.secdev.org/projects/scapy/)
* Paramiko (http://paramiko-docs.readthedocs.org/en/1.16/)

<a name="bundled-sources"></a>
Bundled Sources
---------------
* measurement-proxy (modified)
	* measurement-proxy is a tool to tunnel network traffic through remote nodes. It needs SSH access on the remote node and the possibility to run user level binaries and create raw sockets. 
	* The tool creates a tun device on the tunnel starting point. The traffic routed to this tun device gets tunneled through the remote node.
	* The measurement-proxy can tunnel TCP, UDP and ICMP traffic
	* The tool was modified for this framework to create the tun device in a static namespace and to copy the resolv.conf of the remote node to the tunnel starting point to use the same domain name server
	* Author: Andreas Loibl
	* Licence: GNU GPLv2

Structure
----------

The framework is implemented as Python 3 and 2.7 modules. The functionalities of the framework are divided into multiple components and implemented as individual modules.
The illustration shows all implemented modules by now and the dependencies between all of them. 
The modules can be divided into five groups:

* Wrapper Modules to organize large scale measurements
* a Controller Module to control single measurements
* Network Modules to establish tunnels and configure the routers
* an Analysis Module to execute first analysis steps
* Mobile Phone Modules to control the phones and send messages

<img src="illustrations/classes.png?raw=true" width="800" height="800" hspace="4"/>

<a name="wrapper-module"></a>
**(1) Wrapper Modules**

The framework contains two different wrappers for large measurement. Both are basically implementing the same tasks.
They are based on country lists as input, build pairs of countries and start the controller with these country pairs.
Furthermore they manage the measurement between all possible pairs in a matrix and they manage the used proxy nodes for each country. The wrapper replaces a proxy node for a country if it is not accessible during a measurement and further proxy nodes are available for this country in the input list.
They log all important events during the measurement and hold a counter to store the results for each country pair
under a unique identifier.

The differences between wrapper.py and wrapper_delta.py are the amount of input files
and how they build country pairs from them.
wrapper.py takes only one country list as input and builds pairs between all countries on this list.
wrapper_delta.py takes multiple country lists as input and builds pairs
between two countries from different input lists but no pairs between countries from the same input list.

<a name="controller-module"></a>
**(2) Controller Module**

The controller takes two proxy nodes with their coordinates and a unique counter as input
and exchanges mobile messages for all mobile messaging applications between those proxy nodes.
The controller executes multiple steps to do this:

* Step1: The controller establishes the tunnels from the routers to the proxy nodes.
* Step2: The controller checks the functionatlity of the tunnels and updates the configuration of the routers.
* Step3: The controller configures the locations of the mobile phones to be consistent with the tunnel endpoints.
* Step4: The controller starts the interception software on the routers.
* Step5: The controller executes all necessary tasks on the mobile phones to exchange messages
* Step6: The interception software is stopped and first analysis steps are started 
* Step7: The controller tears down the tunnels and returns the routers and mobile phones to a clean state

<a name="network-modules"></a>
**(3) Network Modules**

The network modules are a module to establish a tunnel,
a component to check the functionality of the tunnel and adapt the DHCP server and restart the DHCP server
and a component that forces a tunnel tear down.

The component to establish a tunnel takes a hostname as input and starts the measurement-proxy as subprocess.
Afterwards it checks regularly if the subprocess is still active.

The component to check the functionality tests the tunnel and the domain name server copied from the remote node
by sending a DNS query. 
If the query results in an error, the check failed and the tunnel could not be established properly.
The network check will return with an error code. The controller has to stop the execution afterwards.
Otherwise the domain name servers are written in the DHCP configuration and the DHCP server is restarted
to propagate the new domain name servers afterwards.

The component to tear down the network tunnel is necessary to allow a clean execution of multiple measurements.
Sometimes, the measurement proxy does not terminate correctly and interfaces for an old tunnel remain on the routers.
They massively interfere with a new tunnel setup.
The module to force a tunnel teardown checks if old measurement processes are still active after they should have
terminated and if so the module forces them to stop.

<a name="mobile-phone-modules"></a>
**(4) Mobile Phone Modules**

The mobile phone controller is divided into multiple modules.
All of these modules base on the adb.py module that provides a class with different basic methods
to interact with the phones. The module illustration shows all implemented methods of the adb.py module by now.
They are kept general and implement single actions like activating a screen or starting a mobile messaging application. Each method is used in multiple modules in the illustration above.
For example the method to activate the screen is used by the module to setup xprivacy and to execute the applications.

The class is instantiated by all mobile phone modules in the illustration above to script different sequences,
e.g. the application execution that has to activate the mobile phone screen, start the mobile messaging application,
enter a conversation, send messages and further steps.
The scripts can be started as Python scripts directly from the controller and don't have to be instantiated.

<a name="analysis-module"></a>
**(5) Analysis Module**

The analysis module executes multiple steps on the resulting network traces.
It uses scapy to analyze network traces and is therefore implemented for Python 2.7.

First, the module extracts all DNS resolutions from the traces and stores the results in text files.
The file names are the domain name combined with unique identifiers.
The files contain all IPs the domain names resolved to.

Second, the module extracts all different network connections as triples of the used transport layer protocol (TCP, UDP),
the according port and the destination IP.

Third, it applies a port and IP filter on all triples, e.g. filtering out all network connections to port 123 (NTP).

Fourth, the module starts path measurements from the proxy node to all IPs of the triples and uses -T or -U
according to the transport layer protocol of the triple and the -p parameter with the port number of the triple.
Those path measurements are used to reproduce the paths of network connections.
The output is stored in text files as well.

Exemplary Setup
-----------------

<a name="controller"></a>
**(1) Controller**

The controller is one of the the two routers. 
No additional hardware device is necessary but all tasks controlling tasks can be solved by a router.
The controller has to have SSH access on the second router to start all necessary tasks on it.

Furthermore, the ADB has to be installed on the controller to interact with the mobile phones.
Both mobile phones are connected to the controller via USB afterwards.

The controller needs the controller modules, the wrapper modules and the mobile phone modules with their config files. 

<a name="routers"></a>
**(2) Routers**

Each router needs to span a wireless network the smartphones can connect to.
The example configuration in this repository holds hostapd configurations. They are configured to secure the wireless network with WPA2.
**Please change the passphrase in the hostapd.conf before using it.**

Furthermore, the routers need DHCP server to configure the mobile phones accordingly when they connect to the network.
The DHCP server have to propagate IP addresses, default gateways and domain name servers.
The example configurations are for the isc-dhcp-server.
They are configured to propagate private addresses out of the address space 10/8 (RFC 1918).
They propagate themselves as default gateway and 1-2 nameservers.

Both routers need SSH access on the remote nodes to establish tunnels.
Furthermore they need all network modules and the analysis module.

<a name="tunnel-network-namespaces"></a>
**(3) Tunnel Network Namespace**

To not interfere with the normal network connections of the routers (e.g. SSH connections to monitor or control them)
the tunnel starting points are created in own network namespaces.
Namespaces are copies of the network stack with individual routing tables, firewall rules and their own network devices.
The wireless devices of the WAPs can not be moved to these network namespaces,
therefore a small workaround is created that routes the traffic from the wireless devices to the network namespaces.

The basic configuration directories for each router contain scripts that create a namespace called "tunnel" on each router.
Afterwards two virtual interfaces are created one called veth0, the other one called veth1.
They are automatically connected to each other and forward the traffic.
veth0 remains in the main namespace and veth1 is pushed to the tunnel namespace.
Afterwards a new routing table called "tunnel" is created in the main namespace to establish policy routing.
The traffic from the wireless device and veth0 is configured to be handled by this new routing table.
The routing table routes the traffic between the wireless device and veth0 and therefore from the wireless device to the tunnel namespace
and the other way round.

<a name="android-mobile-phones"></a>
**(4) Android Mobile Phones**

The USB-Debugging mode has to be activated on the mobile phones to allow the controller to execute commands
over the ADB on the mobile phones.
The USB-Debugging mode can be activated in the developer options on the Android mobile phones.
The developer options can be activated by tapping multiple times on the Buildnumber in the device informations
in the settings on most Android mobile phones. The developer options should be visible afterwards in the settings. This procedure can be different for each mobile phones. The described procedure worked for Samsung Galaxy S3 and Motorola Moto E (2. Generation)

The Android mobile phones have to be rooted to allow the mobile phone controller to execute all tasks.
Enabling and disabling the "wifi" service requires root access.
Furthermore, the mobile phones should support the XPrivacy pro version and iptables.
They require root as well.
Both functionalities can be turned off in the framework configurations if they are not available on the mobile phones
but they improve the measurements and support the analysis.

XPrivacy is used in the framework to change the GPS coordinates of the mobile phones and adapt them to the locations of the proxy nodes
the network traffic is tunneled through. 
The location category should be restricted for all measured applications.
The framework provides methods to change the longitude and latitude value XPrivacy will send to the applications
if they request them.
To do so, the import activity provided by the XPrivacy pro version is used.
It allows the import from an XML file.
The activity only opens a file manager on the mobile phone.
The file manager opens at the recently used location on the smartphone storage.
Therefore the import has to be done once manually before the measurements with the framework
and the import file has to be copied to the same directory and overwrite the old file for each new location. 
The controller will click on this file and confirm the import afterwards.

iptables is used to set up firewalls on the mobile phones.
The firewall is set up by the framework automatically but needs all necessary UIDs to allow a functional performance
on the mobile phones.

<a name="backup-storage"></a>
**(5) Backup Storage**
The framework is built to run on commodity hardware.
Therefore it is recommendable to backup the results (network traces, path measurement outputs) on a secure backup storage.
The controller.py executes a command after all message exchanges and analysis steps for a country pair to store the results.
The command can be given in the controller configuration.

<a name="framework-configuration"></a>
**(6) Framework Configuration**

* wrapper(_delta).ini
The storage directory is used to store the traces from the traffic interception, all videos and the results from the analysis steps.
The directory needs subdirectories for all applications (whatsapp, threema, textsecure, wechat and xprivacy)

The log file created during the measurement can be named here.

The wrapper needs one input file with countries hostnames and their coordinates.

The wrapper_delta takes more than one input file. The number of input files has to be given in the general section and the input files have to be named under an own section input_files.


* controller.ini
General: The worker defines the second router.  SSH authentification data to access this worker has to be added to the configuration.

Location: The location setup section holds the command that changes the GPS coordinates of the mobile phones.
The framework supports the Xprivacy pro version to change coordinates and import the longitude and latitude with the xprivacy_setup.py module.

Network Setup: The network setup section holds the command to establish the tunnel on both routers. The given command executes a python module that starts and controls the measurement proxy establishment.

Network Check: The network check holds commands to check the functionality of the tunnels on both routers. 

Measurement: The measurement section holds the commands that are started on each router to intercept the network traffic.

App Execution: The app execution is described by one command to be executed for each application on the controller.
A second command is necessary to bring the mobile phones back to a clean state if an error occurred.
The framework provides an application execution module that exchanges mobile messages and a clean up module
to terminate running applications and deactivate the mobile phone screen and network connection.

Analysis: The analysis commands are executed as subprocesses on the two routers.
The framework provides the analysis modules as implementation that can be executed here.

Save: A command can be added that is executed at the end of all application execution to store the results on a secure backup storage.
A possible command is a rsync of the storage directory of each router to a backup server. 

* network.ini

The network module can execute different steps.
The steps need to be commands that can be executed in the shell.
A hostname is available as parameter if the command needs it.
If the command ends, the module waits actively for a return value.
Otherwise it waits the given timeout and controls regularly if the process is still running or terminated with an error.

* network_check.ini

The network_check module executes steps similar to the network module, 
but only commands that terminate. The module waits actively for all return values. 

* adb.ini

The devices are defined by their unique serial number. The numbers can be listed with "adb devices".

applicationName is the Android internal package name.
"adb shell pm list packages -f" prints a list of all installed applications and their storage path (path/app.apk)
on the standard output.

startActivity is an application activity that can be used with "adb am start" to open an application.
It is written in the AndordManifest.xml of each package. 
The AndordManifest.xml is contained in the .apk of each application.
"adb pull 'path/app.app'" pulls the file to the controller.
Afterwards the AndroidManifest can be accessed with "aapt dump badging path/app.apk" (http://developer.android.com/tools/help/index.html).

All coordinates have to be determined manually. 
Coordinates can be displayed with the command "adb shell getevent -l". It shows the coordinates the standard output where an action on the screen happens on while interacting with the screen by hand. 

The UIDs for each application are necessary for the according iptabels rules to apply a user match on outgoing traffic..
The output of "adb shell su -c "cat /data/system/packages.xml | grep ('app'|'uid')"" contains the uid for an application
or an application name for a uid.

* analysis.ini

The analysis config holds information about the used path measurement method.
The default method is traceroute.

Blacklisted IPs and ports in the configuration are not considered.
The ip_address should be the IP of the mobile phone. Path measurements will not be made to this IP.
The path measurements are directly started on the remote node via SSH.
Therefore the configuration needs valid SSH authentification data for the remote nodes.
TCP path measurements need root access on the remote nodes.
