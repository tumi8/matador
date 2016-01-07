#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <net/if.h>
#include <netpacket/packet.h>
#include <netinet/in.h>
#include <netinet/ip_icmp.h>
#include <netinet/tcp.h>
#include <netinet/udp.h>
#include <netinet/if_ether.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/select.h>
#include <sys/ioctl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <string.h>

#define BUFLEN 65535

#include "ministun.h"
#include "tools.h"

extern char *stunserver;
extern int stunport;
extern int stuncount;
extern int stundebug;
extern int stun_request(int s, struct sockaddr_in *dst,
    const char *username, struct sockaddr_in *answer);
extern int bind_public(int sockfd, const struct sockaddr *addr, socklen_t addrlen);

struct pseudo_hdr
{
    uint32_t saddr;
    uint32_t daddr;
    uint8_t zero;
    uint8_t proto;
    uint16_t len;
};

struct arp_hdr {
    uint16_t htype;
    uint16_t ptype;
    uint8_t hlen;
    uint8_t plen;
    uint16_t opcode;
    uint8_t sender_mac[6];
    uint8_t sender_ip[4];
    uint8_t target_mac[6];
    uint8_t target_ip[4];
};

int fd_udp_port[FD_SETSIZE], maxfd;

int main(int argc, char **argv)
{
    int i, rc;
    char buffer[BUFLEN];
    uint8_t arp[sizeof(struct ethhdr) + sizeof(struct arp_hdr)];

    if(argc != 5)
    {
        fprintf(stderr, "Usage: %s <interface> <listen-port> <remote-host> <remote-port>\n\n", argv[0]);
        return(1);
    }

    memset(fd_udp_port, 0, sizeof(fd_udp_port));
    
    int port = atoi(argv[2]);
    char *iface_out = argv[1];
    char *rhost = argv[3];
    int rport = atoi(argv[4]);

    int sock_udp = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    int sock_raw_recv = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    int sock_raw_send = socket(AF_INET, SOCK_RAW, IPPROTO_RAW);
    setsockopt(sock_raw_recv, SOL_SOCKET, SO_BINDTODEVICE, iface_out, 4);
    setsockopt(sock_raw_send, SOL_SOCKET, SO_BINDTODEVICE, iface_out, 4);
    int on = 1;
    setsockopt(sock_raw_send, IPPROTO_IP, IP_HDRINCL, &on, sizeof(on));

    ssize_t recsize;
    struct sockaddr_in udp_listen_addr, udp_client_addr, other_addr;
    socklen_t slen = sizeof(struct sockaddr_in);
    socklen_t udp_client_addr_size = slen;
    udp_listen_addr.sin_family = AF_INET;
    udp_listen_addr.sin_addr.s_addr = INADDR_ANY;
    if(port == 0)
    {
        srand(time(NULL));
        do
        {
            port = 6001 + rand() % 22000; // random port 6001-28000
            udp_listen_addr.sin_port = htons(port);

            rc = bind_public(sock_udp,(struct sockaddr *)&udp_listen_addr, sizeof(udp_listen_addr));
        } while(rc == -1);
    }
    else
    {
        udp_listen_addr.sin_port = htons(port);
        rc = bind_public(sock_udp,(struct sockaddr *)&udp_listen_addr, sizeof(udp_listen_addr));
    }

    if(rc == -1)
    {
        perror("error bind failed");
        close(sock_udp);
        fprintf(stderr, "(is another tunnel or socat process already running?)\n");
        exit(EXIT_FAILURE);
    }
    DEBUG_PRINT("Listening on port %i...\n", port);

    // Find interface index from interface name and store index in
    // struct sockaddr_ll device, which will be used as an argument of sendto().
    struct sockaddr_ll device;
    memset(&device, 0, sizeof(struct sockaddr_ll));
    device.sll_family = AF_PACKET;
    device.sll_halen = 6;
    if((device.sll_ifindex = if_nametoindex(iface_out)) == 0) {
      perror("if_nametoindex() failed to obtain interface index ");
      exit(EXIT_FAILURE);
    }
    DEBUG_PRINT("Index for interface %s is %i\n", iface_out, device.sll_ifindex);

    struct ifreq ifr;
    ifr.ifr_addr.sa_family = AF_INET;
    strncpy(ifr.ifr_name, iface_out, IFNAMSIZ-1);

    // get MAC address of iface_out
    if(ioctl(sock_raw_send, SIOCGIFHWADDR, &ifr) < 0)
    {
        perror("ioctl() failed to get source MAC address ");
        exit(EXIT_FAILURE);
    }
    uint8_t if_raw_mac[6];
    memcpy(if_raw_mac, ifr.ifr_hwaddr.sa_data, 6 * sizeof(uint8_t));
    memcpy(device.sll_addr, ifr.ifr_hwaddr.sa_data, 6 * sizeof (uint8_t));
    DEBUG_PRINT("MAC address for interface %s is ", iface_out);
    for(i=0; i<5; i++) {
        DEBUG_PRINT("%02x:", if_raw_mac[i]);
    }
    DEBUG_PRINT("%02x\n", if_raw_mac[5]);

    // get IP address address of iface_out
    if(ioctl(sock_raw_send, SIOCGIFADDR, &ifr) < 0)
    {
        perror("ioctl() failed to get interface IP address");
        exit(EXIT_FAILURE);
    }
    struct in_addr if_raw_addr = ((struct sockaddr_in *)&ifr.ifr_addr)->sin_addr;
    printf("TUNIP=%s \n",inet_ntoa(if_raw_addr));
    DEBUG_PRINT("Rewriting IP source address to %s\n", inet_ntoa(if_raw_addr));

    // send gratuitous ARP
    DEBUG_PRINT("Sending gratuitous ARP to map ");
    for(i=0; i<5; i++) {
        DEBUG_PRINT("%02x:", if_raw_mac[i]);
    }
    DEBUG_PRINT("%02x to %s\n", if_raw_mac[5], inet_ntoa(if_raw_addr));
    memset(arp, 0, sizeof(arp));
    struct ethhdr *arp_ethhdr = (void *)arp;
    struct arp_hdr *arp_arphdr = (void *)arp + sizeof(struct ethhdr);
    arp_arphdr->htype = htons(1);
    arp_arphdr->ptype = htons(ETH_P_IP);
    arp_arphdr->hlen = 6;
    arp_arphdr->plen = 4;
    arp_arphdr->opcode = htons(2); // 1 = ARP request, 2 = ARP reply
    memcpy(arp_arphdr->sender_mac, if_raw_mac, 6 * sizeof(uint8_t));
    memcpy(arp_arphdr->sender_ip, &if_raw_addr.s_addr, 4 * sizeof(uint8_t));
    memcpy(arp_arphdr->target_mac, if_raw_mac, 6 * sizeof(uint8_t));
    memcpy(arp_arphdr->target_ip, &if_raw_addr.s_addr, 4 * sizeof(uint8_t));
    memcpy(arp_ethhdr->h_source, if_raw_mac, 6 * sizeof (uint8_t));
    memset(arp_ethhdr->h_dest, 0xff, 6 * sizeof (uint8_t));
    arp_ethhdr->h_proto = htons(ETH_P_ARP);
    int bytes_sent = sendto(sock_raw_recv, arp, sizeof(arp), 0,(struct sockaddr*)&device, sizeof(device));
    if(bytes_sent != sizeof(arp))
    {
        perror("sendto(arp) failed");
    }

    struct sockaddr_in server,mapped;
    struct hostent *hostinfo;

    hostinfo = gethostbyname(stunserver);
    if (!hostinfo) {
        fprintf(stderr, "Error resolving host %s\n", stunserver);
        return -1;
    }
    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_addr = *(struct in_addr*) hostinfo->h_addr;
    server.sin_port = htons(stunport);

    int res = stun_request(sock_udp, &server, NULL, &mapped);
    if (!res && (mapped.sin_addr.s_addr != htonl(INADDR_ANY)))
    {
        printf("CONNECT=%s:",inet_ntoa(mapped.sin_addr));
        printf("%d\n",htons(mapped.sin_port));
    }
    DEBUG_PRINT("Sending \"OPEN!\" packet to remote host (for UDP hole punching)\n");

    hostinfo = gethostbyname(rhost);
    if(!hostinfo) {
        fprintf(stderr, "Error resolving remote-host\n");
        return -1;
    }
    memset(&udp_client_addr, 0, sizeof(udp_client_addr));
    udp_client_addr.sin_family = AF_INET;
    udp_client_addr.sin_addr = *(struct in_addr*) hostinfo->h_addr;
    udp_client_addr.sin_port = htons(rport);
    strcpy(buffer, "OPEN!");
    sendto(sock_udp, buffer, 5, 0,(struct sockaddr*)&udp_client_addr, udp_client_addr_size);

    DEBUG_PRINT("Waiting for connection from remote host...\n");
    recsize = recvfrom(sock_udp, (void *)buffer, BUFLEN, 0, (struct sockaddr *)&udp_client_addr, &udp_client_addr_size);
    if(recsize == -1)
    {
        perror("recv error");
        close(sock_udp);
        close(sock_raw_recv);
        close(sock_raw_send);
        exit(EXIT_FAILURE);
    }
    DEBUG_PRINT("Received packet from %s:%d\n", inet_ntoa(udp_client_addr.sin_addr), ntohs(udp_client_addr.sin_port));

    fd_set rset;
    FD_ZERO(&rset);
    maxfd = sock_raw_send;
    int eof_socket = 0;
    while(!eof_socket)
    {
        int res = -1;
        FD_SET(sock_udp, &rset);
        FD_SET(sock_raw_recv, &rset);
        FD_SET(sock_raw_send, &rset);
        int sock_fake;
        for(sock_fake = maxfd + 1; sock_fake <= maxfd; sock_fake++)
        {
            FD_SET(sock_fake, &rset);
        }
        res = select(maxfd + 1, &rset, 0, 0, 0);
        if(res < 0) {
            fprintf(stderr, "select failed!\n");
            exit(EXIT_FAILURE);
        }
        if(FD_ISSET(sock_raw_recv, &rset))
        {
            slen = sizeof(struct sockaddr_in);
            recsize = recvfrom(sock_raw_recv, (void *)buffer, BUFLEN, 0, (struct sockaddr *)&other_addr, &slen);
            if(recsize > 0)
            {
                struct ethhdr *eth = (struct ethhdr *)buffer;
                if(ntohs(eth->h_proto) == ETH_P_ARP)
                {
                    struct arp_hdr *packet = (void *)buffer + sizeof(struct ethhdr);
                    if(ntohs(packet->opcode) == 1) // ARP request
                    {
                        /* printf("Received ARP request from RAW socket\n"); */
                        /* printf("target_ip: %s\n", inet_ntoa(*(struct in_addr *)&packet->target_ip)); */
                        if(0 == memcmp(&packet->target_ip, &if_raw_addr.s_addr, 4 * sizeof(uint8_t))) // our IP
                        {
                            DEBUG_PRINT("Received ARP request for our IP from RAW socket, replying...\n");
                            // send ARP reply back to the sender of the ARP request
                            memcpy(arp_ethhdr->h_dest, packet->sender_mac, 6 * sizeof (uint8_t));
                            int bytes_sent = sendto(sock_raw_recv, arp, sizeof(arp), 0,(struct sockaddr*)&device, sizeof(device));
                            if(bytes_sent != sizeof(arp))
                            {
                                perror("sendto(arp) failed");
                            }
                        }
                    }
                }
                else if(ntohs(eth->h_proto) == ETH_P_IP)
                {
                    struct iphdr *packet = (void *)buffer + sizeof(struct ethhdr);
                    if(packet->daddr == if_raw_addr.s_addr)
                    {
                        DEBUG_PRINT("Received IP packet from RAW socket: ");
                        DEBUG_PRINT("%s -> ", inet_ntoa(*(struct in_addr *)&packet->saddr));
                        DEBUG_PRINT("%s\n", inet_ntoa(*(struct in_addr *)&packet->daddr));

                        int skip = 0;

                        if(packet->protocol == IPPROTO_ICMP)
                        {
                            struct icmphdr *data = (void *)buffer + sizeof(struct ethhdr) + sizeof(struct iphdr);
                            if(data->type == ICMP_ECHOREPLY)
                            {
                                DEBUG_PRINT("Protocol: ICMP, echo reply, id: %x\n", data->un.echo.id);
                            }
                            else
                            {
                                DEBUG_PRINT("Protocol: ICMP, type: %d, code: %d\n", data->type, data->code);
                            }
                        }
                        else if(packet->protocol == IPPROTO_TCP)
                        {
                            struct tcphdr *data = (void *)packet + sizeof(struct iphdr);
                            DEBUG_PRINT("Protocol: TCP, sport: %d, dport: %d\n", htons(data->source), htons(data->dest));

                            DEBUG_PRINT("If we had a TCP stack we'd have to feed this packet into it, but now we're skipping it.\n");
                            skip = 1;
                        }
                        else if(packet->protocol == IPPROTO_UDP)
                        {
                            struct udphdr *data = (void *)packet + sizeof(struct iphdr);
                            DEBUG_PRINT("Protocol: UDP, sport: %d, dport: %d\n", htons(data->source), htons(data->dest));
                            if(packet->saddr == udp_client_addr.sin_addr.s_addr)
                            {
                                if(htons(data->source) == rport && htons(data->dest) == port)
                                {
                                    DEBUG_PRINT("Skipping packet, this is our own UDP tunnel!\n");
                                    skip = 1;
                                }
                            }
                        }
                        else
                        {
                            DEBUG_PRINT("Unknown protocol: %d\n", packet->protocol);
                        }
                        if(skip == 0)
                        {
                            int bytes_sent = sendto(sock_udp, packet, recsize-sizeof(struct ethhdr), 0,(struct sockaddr*)&udp_client_addr, udp_client_addr_size);
                            if(bytes_sent != recsize-sizeof(struct ethhdr))
                            {
                                perror("sendto() failed");
                                DEBUG_PRINT("tried sending to %s:%d\n", inet_ntoa(udp_client_addr.sin_addr), ntohs(udp_client_addr.sin_port));
                                hexDump("packet", packet, recsize-sizeof(struct ethhdr));
                                hexDump("udp_client_addr", &udp_client_addr, udp_client_addr_size);
                            }
                        }
                    }
                }
            }
        }
        if(FD_ISSET(sock_udp, &rset))
        {
            slen = sizeof(struct sockaddr_in);
            recsize = recvfrom(sock_udp, (void *)buffer, BUFLEN, 0, (struct sockaddr *)&other_addr, &slen);
            if(recsize == 4 && strcmp(buffer, "EXIT") == 0)
            {
                eof_socket = 1;
            }
            else if(recsize > 0)
            {
                DEBUG_PRINT("Received packet from UDP socket\n");

                struct iphdr *packet = (struct iphdr *)buffer;
                struct in_addr in_addr_source, in_addr_dest;
                in_addr_source.s_addr = packet->saddr;
                in_addr_dest.s_addr = packet->daddr;
                struct sockaddr_in dest_addr;
                dest_addr.sin_family = AF_INET;
                dest_addr.sin_addr = in_addr_dest;
                DEBUG_PRINT("saddr: %s ", inet_ntoa(in_addr_source));
                DEBUG_PRINT("daddr: %s\n", inet_ntoa(in_addr_dest));

                /* hexDump("buffer", &buffer, recsize); */

                if(packet->protocol == IPPROTO_ICMP)
                {
                    struct icmphdr *data = (void *)buffer + sizeof(struct iphdr);

                    DEBUG_PRINT("Protocol: ICMP, id: %x\n", data->un.echo.id);

                    if(-1 == sendto(sock_raw_send, buffer, recsize, 0,(struct sockaddr*)&dest_addr, sizeof(dest_addr)))
                    {
                        perror("sendto() failed");
                    }
                }
                else if(packet->protocol == IPPROTO_TCP)
                {
                    // TCP should be handled by the other tunnel endpoint via tun2socks and not actually be sent through the UDP tunnel...

                    struct tcphdr *data = (void *)buffer + sizeof(struct iphdr);

                    DEBUG_PRINT("Protocol: TCP, sport: %d, dport: %d - what is this packet doing here?\n", htons(data->source), htons(data->dest));
                }
                else if(packet->protocol == IPPROTO_UDP)
                {
                    struct udphdr *data = (void *)buffer + sizeof(struct iphdr);

                    DEBUG_PRINT("Protocol: UDP, sport: %d, dport: %d\n", htons(data->source), htons(data->dest));

                    // open and bind a UDP socket on the source port so the kernel doesn't send ICMP unreachable packets
                    int sock_fake_udp = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
                    struct sockaddr_in fake_addr;
                    fake_addr.sin_family = AF_INET;
                    fake_addr.sin_addr.s_addr = INADDR_ANY;
                    fake_addr.sin_port = data->source;
                    if(-1 == bind_public(sock_fake_udp,(struct sockaddr *)&fake_addr, sizeof(struct sockaddr_in)))
                    {
                        perror("bind() failed");
                    }
                    fd_udp_port[sock_fake_udp] = htons(data->dest);
                    maxfd = sock_fake_udp;

                    if(-1 == sendto(sock_raw_send, buffer, recsize, 0,(struct sockaddr*)&dest_addr, sizeof(dest_addr)))
                    {
                        perror("sendto() failed");
                    }
                }
                else
                {
                    if(-1 == sendto(sock_raw_send, buffer, recsize, 0,(struct sockaddr*)&dest_addr, sizeof(dest_addr)))
                    {
                        perror("sendto() failed");
                    }
                }
            }
            else eof_socket = 1;
        }
        for(sock_fake = sock_raw_send + 1; sock_fake <= maxfd; sock_fake++)
        {
            if(FD_ISSET(sock_fake, &rset))
            {
                slen = sizeof(struct sockaddr_in);
                // just empty the socket's recv buffer and discard the data,
                // it is read and forwarded by the RAW socket sock_raw_recv
                recsize = recvfrom(sock_fake, (void *)buffer, BUFLEN, 0, (struct sockaddr *)&other_addr, &slen);
            }
        }
    }
    return(0);
}

