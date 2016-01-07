#!/bin/sh -e
#The script sets up an own network namespace for the tunnel namespace
#and configures policy routing to route all traffic between the namespace and the wireless device


#add a new routing table for polcy routing
echo 200 tunnel >> /etc/iproute2/rt_tables

# creates a new network namespace named tunnle
ip netns add tunnel

# adds two virtuel interfaces one in the main namespace one in the tunnel namespace and configures them
ip link add dev veth0 type veth peer name veth1
ip link set veth1 netns tunnel
ip a add 10.1.1.1/24 dev veth0
ip netns exec tunnel ip a add 10.1.1.2/24 dev veth1
ip l set veth0 up
ip netns exec tunnel ip l set veth1 up

#adds a rule to the routing table to forward all traffic from wlan0 and veth0 to the routing table tunnel
ip rule add iif wlan0 table tunnel
ip rule add iif veth0 table tunnel
#the defualt route is to veth1 in the tunnel namesapce
ip r add default via 10.1.1.2 table tunnel
ip route add 10.0.0.0/29 dev wlan0 table tunnel
ip netns exec tunnel ip r add 10.0.0.0/29 via 10.1.1.1 dev veth1

#configures NAT in the tunnel namespace
ip netns exec tunnel iptables --table nat --append POSTROUTING -s 10.1.1.0/24  ! -d 10.1.1.0/24 -j MASQUERADE
ip netns exec tunnel iptables --table nat --append POSTROUTING -s 10.0.0.0/29 ! -d 10.0.0.0/29 -j MASQUERADE

exit 0