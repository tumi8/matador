*********************
* measurement-proxy *
*********************

This is a bundled pre-version of a tool developed by Andreas Loibl. 
Upon completion, it will be released on its own.


Features
********

* UDP tunnel (no TCP meltdown due to TCP-over-TCP tunneling)
* automatic NAT traversal using STUN and UDP hole punching
* very lightweight "proxy" binary:
  - tiny binary (< 50 KB when built without debug and with dietlibc)
  - statically linked, no dependencies
  - multilib support, compiled for 64 and 32 bit architectures
  - only relies on raw sockets, i.e. it does NOT depend on:
    - TUN/TAP devices
    - iptables
    - ip addr add, sysctl, ...
    - SSH tunneling
  - transparent tunneling of packets:
    - does not change source ports of tunneled packets
    - does not appear as additional hop in e.g. traceroute
* tunnel setup fully automated by "tunnel" binary:
  - takes care of NAT traversal in both directions
  - uses SSH to upload and run the "proxy"-binary on the remote node
  - creates a TUN device locally where you can simply route packets to


Building
********

Make sure your system has all build dependencies installed (see below).
Then you can simply use "make" to compile the software, for example:

  if you want/don't want to use dietlibc: diet/fat
    make fat all
    make diet all

  if you want debugging symbols and debug output: debug
	make debug all
    make debug fat all
    make debug diet all

  if your 64 bit build system doesn't support multilib: singlearch
    make singlearch
    make fat singlearch
    make diet singlearch
    make debug fat singlearch
    make debug diet singlearch

  when switching between build variants or to clean up:
    make clean

Build dependencies
******************

* GNU Make
  for Debian/Ubuntu: apt-get install make

* GCC
  for Debian/Ubuntu: apt-get install gcc-multilib

* libssh - mulitplatform C library implementing the SSHv2 and SSHv1 protocol
  https://www.libssh.org/
  for Debian/Ubuntu: apt-get install libssh-dev

* diet libc (optional) - a libc optimized for small size
  http://www.fefe.de/dietlibc/
  reduces the size of the statically compiled "proxy"-binary,
  will only be used if "make" can find "diet" in your $PATH

  to compile and install dietlibc with multilib support (if your build system
  is 64bit and you want to be able to compile 32bit binaries):
    make && make i386
    sudo make install && sudo make ARCH=i386 install
    export PATH="$PATH:/opt/diet/bin"


Runtime dependencies
********************

proxy:
  * root privileges (will be run using sudo)

tunnel:
  * libssh
  * root privileges to create TUN device


Usage
*****

tunnel [options...] [<ssh_user>@]<remote_host>[:<remote_port>] -- [<scanner_command> [<scanner_args>...]]

  <remote_host>
     remote host where the proxy will be started
  <remote_port>
     remote UDP port where the proxy is listening (default: random)

Options:
  -I <interface>
     interface to bind to (default: eth0)
  -T <tun_device>
     name of TUN-device for tunnel (default: automatic)
  -S <stun_server>[:<stun_port>]
     STUN server for external IP lookup (default: stun.schlund.de:3478)
  -s <ssh_host>[:<ssh_port>]
     specify different remote host for SSH connection (default: <remote_host>:22)
  -D <ssh_socks_port>
     SSH dynamic port forwarding port (default: 8880)
  -l <ssh_user>
     username to login for SSH connection
  -i <ssh_keyfile>
     private key for SSH public key authentication
  -p <ssh_password>
     password to login for SSH connection
  -n <nameserver>
     IP of (public) nameserver to use (default: 8.8.8.8)
  -e su|sudo
     local command to elevate privileges (default on this machine: su)
  -E su|sudo
     remote command to elevate privileges via SSH (default: sudo)
  -P <local_port>
     local UDP port to listen on (default: random)


Usage examples
**************

Shell with tunneled network traffic
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
user@client$ sudo ./tunnel tumple_proxy@planetlab3.net.in.tum.de
OK, our tunnel endpoint is reachable externally via 188.192.216.17:22879
SSH connection established.
Executing command via SSH: sudo killall proxy; echo "ARCH"=$(getconf LONG_BIT)
File to upload: proxy
uploading proxy... 76243/76243 bytes (100%)
Executing command via SSH: sudo -S ./proxy eth0 0 188.192.216.17 22879 &
Finished SSH session...
Proxy is listening at 138.246.253.3:16025
Sending "OPEN!" packet to remote host (for UDP hole punching)
Tunnel is established!
NOTICE(tun2socks): initializing BadVPN tun2socks 1.999.130
Waiting for TUN device...
NOTICE(tun2socks): entering event loop
root@client# (now you have a shell with all it's network traffic tunneled through the tunnel)
root@client# exit
NOTICE(tun2socks): exiting

Run measurements (example: traceroute)
^^^^^^^^^^^^^^^^
user@client$ sudo ./tunnel tumple_proxy@planetlab3.net.in.tum.de -- traceroute 8.8.8.8
OK, our tunnel endpoint is reachable externally via 188.192.216.17:18063
SSH connection established.
Executing command via SSH: sudo killall proxy; echo "ARCH"=$(getconf LONG_BIT)
File to upload: proxy
uploading proxy... 76243/76243 bytes (100%)
Executing command via SSH: sudo -S ./proxy eth0 0 188.192.216.17 18063 &
Finished SSH session...
Proxy is listening at 138.246.253.3:19738
Sending "OPEN!" packet to remote host (for UDP hole punching)
Tunnel is established!
NOTICE(tun2socks): initializing BadVPN tun2socks 1.999.130
Waiting for TUN device...
NOTICE(tun2socks): entering event loop
traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.122.1 (192.168.122.1)  34.052 ms  34.036 ms  36.283 ms
 2  planetlab-gw.net.in.tum.de (138.246.253.254)  37.150 ms  42.298 ms  42.332 ms
 3  nz-csr1-kw5-bb1.informatik.tu-muenchen.de (131.159.252.2)  36.381 ms  36.376 ms  36.369 ms
 4  cr-erl1-be4-147.x-win.dfn.de (188.1.241.193)  40.701 ms  42.133 ms  42.127 ms
 5  cr-fra1-hundredgige0-1-0-0-7.x-win.dfn.de (188.1.144.102)  47.723 ms  47.962 ms  49.542 ms
 6  de-cix20.net.google.com (80.81.193.108)  46.309 ms  42.069 ms  41.988 ms
 7  216.239.47.251 (216.239.47.251)  43.334 ms 216.239.48.1 (216.239.48.1)  43.212 ms 216.239.48.3 (216.239.48.3)  43.145 ms
 8  209.85.241.41 (209.85.241.41)  44.170 ms 72.14.238.143 (72.14.238.143)  44.454 ms 216.239.49.73 (216.239.49.73)  44.447 ms
 9  google-public-dns-a.google.com (8.8.8.8)  43.197 ms  44.332 ms  44.534 ms
NOTICE(tun2socks): exiting


Bundled external sources
************************

ministun.c, ministun.h
    Minimalistic STUN client
    Author: Vladislav Grishenko <themiron@mail.ru>
    License: GNU GPL v2
    URL: https://code.google.com/p/ministun/

tools.c: hexDump()
    Function to print hex dump of arbitrary memory
    Author: paxdiablo
    URL: http://stackoverflow.com/a/7776146/3330540

bind_public.c (modified)
    Re-map bind() on 0.0.0.0 or :: to bind() on the node's public IP address
    Author: Jude Nelson <jcnelson@cs.princeton.edu>
    VCS: git://git.planet-lab.org/bind_public.git
    URL: http://git.planet-lab.org/?p=bind_public.git

tun2socks (modified)
    a program that "socksifes" TCP connections at the network layer. It implements a TUN device
    which accepts all incoming TCP connections (regardless of destination IP), and forwards the
    connections through a SOCKS server
    see tun2socks/README for more details
    Author: Ambroz Bizjak <ambrop7@gmail.com>
    License: BSD 3
    URL: https://github.com/ambrop72/badvpn

