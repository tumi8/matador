#define _GNU_SOURCE
#include <errno.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <netinet/ip_icmp.h>
#include <netinet/udp.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <string.h>
#include <signal.h>
#include <termios.h>
#include <libssh/libssh.h>
#include <libssh/legacy.h>
#include <linux/if_tun.h>
#include <linux/ioctl.h>
#include <sched.h>



#include "ministun.h"
#include "tools.h"

#define BUFLEN 65535
#define IFNAMSIZ 16

char *proxy_filename = "proxy";
char *proxy_filename_with_location = "/home/measurement-proxy/proxy";
char proxy_filename_arch[16]; // space for proxy-filename + arch extension
int use_sudo_local = 0, use_sudo_remote = 1;
struct sockaddr_in udp_server_addr;
int sock_udp_tun = 0;

extern char *stunserver;
extern int stunport;
extern int stuncount;
extern int stundebug;
extern int stun_request(int s, struct sockaddr_in *dst, const char *username, struct sockaddr_in *answer);
extern void tun2socks_write(const uint8_t *data, int data_len);
extern char *tun2socks_getifname();
extern int tun2socks_init(char *tundev, char *ipaddr, char *netmask, char *socksaddr, void *callback);
extern void tun2socks_run();

static void usage(char *name)
{
    /* fprintf(stderr, "Usage: %s [-I <interface>] [-T <tun_device>] [-S <stun_server>[:<stun_port>]] [-P <local_port>] [-s <ssh_host>[:<ssh_port>]] [-l <ssh_user>] [-p <ssh_password>] [-i <ssh_keyfile>] [-D <ssh_socks_port>] [-n <nameserver>] [-e su|sudo] [-E su|sudo] [<ssh_user>@]<remote_host>[:<remote_port>] -- [<scanner_command> [<scanner_args>...]]\n", name); */
    fprintf(stderr, "Usage: %s [options...] [<ssh_user>@]<remote_host>[:<remote_port>] -- [<scanner_command> [<scanner_args>...]]\n", name);
    fprintf(stderr, "\n  <remote_host>\n"
                    "     remote host where the proxy will be started\n");
    fprintf(stderr, "  <remote_port>\n"
                    "     remote UDP port where the proxy is listening (default: random)\n");
    fprintf(stderr, "\nOptions:\n");
    fprintf(stderr, "  -I <interface>\n"
                    "     interface to bind to (default: %s)\n", DEFAULT_INTERFACE);
    fprintf(stderr, "  -T <tun_device>\n"
                    "     name of TUN-device for tunnel (default: automatic)\n");
    fprintf(stderr, "  -S <stun_server>[:<stun_port>]\n"
                    "     STUN server for external IP lookup (default: %s:%d)\n", stunserver, stunport);
    fprintf(stderr, "  -s <ssh_host>[:<ssh_port>]\n"
                    "     specify different remote host for SSH connection (default: <remote_host>:22)\n");
    fprintf(stderr, "  -D <ssh_socks_port>\n"
                    "     SSH dynamic port forwarding port (default: %d)\n", DEFAULT_SOCKSPORT);
    fprintf(stderr, "  -l <ssh_user>\n"
                    "     username to login for SSH connection\n");
    fprintf(stderr, "  -i <ssh_keyfile>\n"
                    "     private key for SSH public key authentication\n");
    fprintf(stderr, "  -p <ssh_password>\n"
                    "     password to login for SSH connection\n");
    fprintf(stderr, "  -n <nameserver>\n"
                    "     IP of (public) nameserver to use (default: %s)\n", DEFAULT_NAMESERVER);
    fprintf(stderr, "  -e su|sudo\n"
                    "     local command to elevate privileges (default on this machine: %s)\n", ((use_sudo_local == 1) ? "sudo" : "su" ));
    fprintf(stderr, "  -E su|sudo\n"
                    "     remote command to elevate privileges via SSH (default: %s)\n", ((use_sudo_remote == 1) ? "sudo" : "su" ));
    fprintf(stderr, "  -P <local_port>\n"
                    "     local UDP port to listen on (default: random)\n");
}

void tun_packet_received(uint8_t *buf, int buf_len)
{
    /* hexDump("packet", buf, buf_len); */
    struct iphdr *packet = (void *)buf;
    if(packet->protocol != IPPROTO_TCP)
    {
        /*
        DEBUG_PRINT("Received IP packet from TUN device: ");
        DEBUG_PRINT("%s -> ", inet_ntoa(*(struct in_addr *)&packet->saddr));
        DEBUG_PRINT("%s\n", inet_ntoa(*(struct in_addr *)&packet->daddr));

        if(packet->protocol == IPPROTO_ICMP)
        {
            struct icmphdr *data = (void *)packet + sizeof(struct iphdr);
            if(data->type == ICMP_ECHOREPLY)
            {
                DEBUG_PRINT("Protocol: ICMP, echo reply, id: %x\n", data->un.echo.id);
            }
            else
            {
                DEBUG_PRINT("Protocol: ICMP, type: %d, code: %d\n", data->type, data->code);
            }
        }
        else if(packet->protocol == IPPROTO_UDP)
        {
            struct udphdr *data = (void *)packet + sizeof(struct iphdr);
            DEBUG_PRINT("Protocol: UDP, sport: %d, dport: %d\n", htons(data->source), htons(data->dest));
        }
        */
        socklen_t slen = sizeof(struct sockaddr_in);
        sendto(sock_udp_tun, buf, buf_len, 0,(struct sockaddr*)&udp_server_addr, slen);
    }
}

int main(int argc, char **argv)
{
    int rc;
    int opt;
    char *colon;
    int port = 0;
    int socksport = DEFAULT_SOCKSPORT;
    char *iface_out = DEFAULT_INTERFACE;
    char *tundevice = DEFAULT_TUNDEVICE;
    char *nameserver = DEFAULT_NAMESERVER;
    char *shost = NULL;
    char *suser = NULL;
    char *spass = NULL;
    char *skeyfile = NULL;
    int sport = 22;

    // check whether sudo is available
    if(0 == system("sudo -nl ip 2>/dev/null | grep -q ip"))
    {
        use_sudo_local = 1;
    }

    while ((opt = getopt(argc, argv, "I:D:T:n:s:l:p:i:S:P:e:E:h")) != -1)
    {
        switch (opt)
        {
            case 'P':
                port = atoi(optarg);
                break;
            case 'D':
                socksport = atoi(optarg);
                break;
            case 'I':
                iface_out = optarg;
                break;
            case 'T':
                tundevice = optarg;
                break;
            case 'n':
                nameserver = optarg;
                break;
            case 's':
                shost = optarg;
                // handle ssh_host:ssh_port
                colon = strchr(shost, ':');
                if(colon)
                {
                    *colon = '\0';
                    sport = strtol(colon + 1, NULL, 10);
                }
                break;
            case 'l':
                suser = optarg;
                break;
            case 'p':
                spass = optarg;
                break;
            case 'i':
                skeyfile = optarg;
                break;
            case 'S':
                stunserver = optarg;
                // handle stun_server:stun_port
                colon = strchr(stunserver, ':');
                if(colon)
                {
                    *colon = '\0';
                    stunport = strtol(colon + 1, NULL, 10);
                }
                break;
            case 'e':
                if(strcmp(optarg, "su") == 0) use_sudo_local=0;
                else if(strcmp(optarg, "sudo") == 0) use_sudo_local=1;
                else 
                {
                    usage(argv[0]);
                    return -1;
                }
                break;
            case 'E':
                if(strcmp(optarg, "su") == 0) use_sudo_remote=0;
                else if(strcmp(optarg, "sudo") == 0) use_sudo_remote=1;
                else 
                {
                    usage(argv[0]);
                    return -1;
                }
                break;
            default:
                usage(argv[0]);
                return -1;
        }
    }
    if(argv[optind] == NULL)
    {
        usage(argv[0]);
        return -1;
    }
    char *rhost = argv[optind];
    int rport = 0;
    // handle remote_host:remote_port
    colon = strchr(rhost, ':');
    if(colon)
    {
        *colon = '\0';
        rport = strtol(colon + 1, NULL, 10);
    }
    // handle ssh_user@remote_host
    colon = strchr(rhost, '@');
    if(colon)
    {
        *colon = '\0';
        suser = rhost; // rhost is now "ssh_user\0..."
        rhost = colon + 1;
    }
    if(shost == NULL) shost = rhost;

    int sock_udp = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    setsockopt(sock_udp, SOL_SOCKET, SO_BINDTODEVICE, iface_out, 4);

    struct sockaddr_in udp_listen_addr;
    udp_listen_addr.sin_family = AF_INET;
    udp_listen_addr.sin_addr.s_addr = INADDR_ANY;
    if(port == 0)
    {
        srand(time(NULL));
        do
        {
            port = 6001 + rand() % 22000; // random port 6001-28000
            udp_listen_addr.sin_port = htons(port);

            rc = bind(sock_udp,(struct sockaddr *)&udp_listen_addr, sizeof(udp_listen_addr));
        } while(rc == -1);
    }
    else
    {
        udp_listen_addr.sin_port = htons(port);
        rc = bind(sock_udp,(struct sockaddr *)&udp_listen_addr, sizeof(udp_listen_addr));
    }
    if(rc == -1)
    {
        perror("error bind failed");
        close(sock_udp);
        fprintf(stderr, "(is another tunnel process already running?)\n");
        exit(EXIT_FAILURE);
    }

    struct sockaddr_in server,mapped;
    struct hostent *hostinfo;

    hostinfo = gethostbyname(stunserver);
    if(!hostinfo) {
        fprintf(stderr, "Error resolving host %s\n", stunserver);
        return -1;
    }
    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_addr = *(struct in_addr*) hostinfo->h_addr;
    server.sin_port = htons(stunport);

    int res = stun_request(sock_udp, &server, NULL, &mapped);
    if(!res && (mapped.sin_addr.s_addr != htonl(INADDR_ANY)))
    {
        DEBUG_PRINT("OK, our tunnel endpoint is reachable externally via %s:",inet_ntoa(mapped.sin_addr));
        DEBUG_PRINT("%d\n",htons(mapped.sin_port));
    }

    ssh_session my_ssh_session = ssh_new();
    if(my_ssh_session == NULL)
    {
        perror("ssh_new() failed");
        exit(EXIT_FAILURE);
    }
    ssh_options_set(my_ssh_session, SSH_OPTIONS_HOST, shost);
    ssh_options_set(my_ssh_session, SSH_OPTIONS_PORT, &sport);
    if(suser && *suser) ssh_options_set(my_ssh_session, SSH_OPTIONS_USER, suser);
    rc = ssh_connect(my_ssh_session);
    if(rc != SSH_OK)
    {
        fprintf(stderr, "Error connecting to localhost: %s\n",
                ssh_get_error(my_ssh_session));
        exit(EXIT_FAILURE);
    }
    /* Get the list of supported authentication schemes.  */
    int methods;
    rc = ssh_userauth_none(my_ssh_session, NULL);
    if(rc == SSH_AUTH_SUCCESS)
    {
        fprintf(stderr, "SSH authentication succeeded using the none method - "
                "should not happen; very old server?\n");
        exit(EXIT_FAILURE);
    }
    else if(rc == SSH_AUTH_DENIED)
    {
        methods = ssh_userauth_list(my_ssh_session, NULL);
    }
    else
    {
        // try all methods
        methods = (SSH_AUTH_METHOD_PASSWORD |
                SSH_AUTH_METHOD_PUBLICKEY |
                SSH_AUTH_METHOD_INTERACTIVE);
    }
    if(spass && (methods & SSH_AUTH_METHOD_PASSWORD))
    {
        rc = ssh_userauth_password(my_ssh_session, NULL, spass);
        if(rc == SSH_AUTH_SUCCESS) goto ssh_auth_done;
    }
    if(skeyfile && (methods & SSH_AUTH_METHOD_PUBLICKEY))
    {
        rc = ssh_userauth_privatekey_file(my_ssh_session, NULL, skeyfile, NULL);
        if(rc == SSH_AUTH_SUCCESS)
        {
            goto ssh_auth_done;
        }
        else
        {
            // command line argument explicitly set keyfile
            // so we don't try any other methods if it fails
            fprintf(stderr, "SSH public key authentication failed: %s\n",
                    ssh_get_error(my_ssh_session));
            exit(EXIT_FAILURE);
        }
    }
    // autopubkey handles authentication via ssh-agent etc.
    rc = ssh_userauth_autopubkey(my_ssh_session, NULL);
ssh_auth_done:
    if(rc != SSH_AUTH_SUCCESS)
    {
        printf("SSH connection NOT established.\n");
        fprintf(stderr, "SSH connection could not be established: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    DEBUG_PRINT("SSH connection established.\n");

    // setup SSH shell
    ssh_channel channel = ssh_channel_new(my_ssh_session);
    if(channel == NULL)
    {
        fprintf(stderr, "Error allocating SSH channel: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    rc = ssh_channel_open_session(channel);
    if(rc != SSH_OK)
    {
        fprintf(stderr, "Error opening SSH session: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_channel_free(channel);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    rc = ssh_channel_request_pty(channel);
    if(rc == SSH_OK) rc = ssh_channel_change_pty_size(channel, 80, 24);
    if(rc == SSH_OK) rc = ssh_channel_request_shell(channel);
    if(rc != SSH_OK)
    {
        fprintf(stderr, "Error requesting PTY and shell: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_channel_free(channel);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    char buffer[BUFLEN];
    // stopping old running proxy
    if(use_sudo_remote == 1)
        sprintf(buffer, "sudo killall %s; echo \"ARCH\"=$(getconf LONG_BIT)", proxy_filename);
    else
        sprintf(buffer, "su -c \"killall %s\"; echo \"ARCH\"=$(getconf LONG_BIT)", proxy_filename);
    DEBUG_PRINT("Executing command via SSH: %s\n", buffer);
    if(ssh_channel_is_open(channel) && !ssh_channel_is_eof(channel))
    {
        ssh_channel_write(channel, buffer, strlen(buffer));
        ssh_channel_write(channel, "\n", 1);
    }
    int nbytes = ssh_channel_read(channel, buffer, sizeof(buffer), 0);
    while(nbytes > 0)
    {
        char *arch = strstr(buffer, "ARCH=");
        if(arch)
        {
            arch += strlen("ARCH=");
            strcat(proxy_filename_arch, proxy_filename_with_location);
            strcat(proxy_filename_arch, "-");
            strncat(proxy_filename_arch, arch, strcspn(arch, "\r\n"));
            break;
        }
        /* if(write(STDOUT_FILENO, buffer, nbytes) != nbytes) */
        /* { */
        /*     fprintf(stderr, "Error reading command output from SSH: %s\n", */
        /*             ssh_get_error(my_ssh_session)); */
        /*     ssh_channel_close(channel); */
        /*     ssh_channel_free(channel); */
        /*     ssh_disconnect(my_ssh_session); */
        /*     ssh_free(my_ssh_session); */
        /*     exit(EXIT_FAILURE); */
        /* } */
        nbytes = ssh_channel_read(channel, buffer, sizeof(buffer), 0);
    }

    // transfer proxy binary via SCP
    ssh_scp scp = ssh_scp_new(my_ssh_session, SSH_SCP_WRITE | SSH_SCP_RECURSIVE, ".");
    if(scp == NULL)
    {
        fprintf(stderr, "Error allocating scp session: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    rc = ssh_scp_init(scp);
    if(rc != SSH_OK)
    {
        fprintf(stderr, "Error initializing scp session: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_scp_free(scp);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    struct stat buf;
    char *upload_filename = proxy_filename_arch;
    if(stat(upload_filename, &buf) < 0) upload_filename = proxy_filename_with_location;
    if(stat(upload_filename, &buf) < 0)
    {
        perror("Can't find proxy binary to upload");
        exit(EXIT_FAILURE);
    }
    DEBUG_PRINT("File to upload: %s\n", upload_filename);
    rc = ssh_scp_push_file(scp, proxy_filename, buf.st_size, S_IRUSR | S_IWUSR | S_IXUSR);
    if(rc != SSH_OK)
    {
        fprintf(stderr, "Can't open remote file: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_scp_close(scp);
        ssh_scp_free(scp);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    int fd = open(upload_filename, O_RDONLY);
    if(fd < 0)
    {
        perror("error opening file");
        ssh_scp_close(scp);
        ssh_scp_free(scp);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    int total = 0;
    do
    {
        int r = read(fd, buffer, sizeof(buffer));
        if(r == 0) break;
        if(r < 0)
        {
            perror("error reading file");
            break;
        }
        rc = ssh_scp_write(scp, buffer, r);
        if(rc == SSH_ERROR)
        {
            fprintf(stderr, "Error writing in scp: %s\n",
                    ssh_get_error(my_ssh_session));
            break;
        }
        total += r;
        DEBUG_PRINT("\ruploading %s... %i/%lu bytes (%d%%)", upload_filename, total, buf.st_size, (int)(100*total/buf.st_size));
    } while(total < buf.st_size);
    DEBUG_PRINT("\n");
    ssh_scp_close(scp);
    char resolv[BUFLEN];
    scp = ssh_scp_new(my_ssh_session, SSH_SCP_READ, "/etc/resolv.conf");
    if(scp == NULL)
    {
        fprintf(stderr, "Error allocating scp session: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    rc = ssh_scp_init(scp);
    if(rc != SSH_OK)
    {
        fprintf(stderr, "Error initializing scp session: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_scp_free(scp);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    rc = ssh_scp_pull_request(scp);
    if(rc != SSH_SCP_REQUEST_NEWFILE)
    {
        fprintf(stderr, "Error receiving information about file: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_scp_close(scp);
        ssh_scp_free(scp);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    int resolv_filesize = ssh_scp_request_get_size(scp);
    ssh_scp_accept_request(scp);
    rc = ssh_scp_read(scp, resolv, resolv_filesize);
    if(rc == SSH_ERROR)
    {
        fprintf(stderr, "Error receiving file data: %s\n",
                ssh_get_error(my_ssh_session));
        ssh_scp_close(scp);
        ssh_scp_free(scp);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }
    ssh_scp_close(scp);
 
	char resolv_filename[64];
	sprintf(resolv_filename, "/etc/netns/tunnel/resolv.conf");
        FILE *f = fopen(resolv_filename, "w");
    	fprintf(f, "%s\n", resolv);
    	fclose(f);
 
    ssh_scp_free(scp);

   /* // write fake resolv.conf
    char resolv_filename[64];
    if(nameserver)
    {
        sprintf(resolv_filename, "/tmp/resolv-%d.conf", getpid());
        FILE *f = fopen(resolv_filename, "w");
        fprintf(f, "nameserver %s\n", nameserver);
        fclose(f);
    }*/

    // running proxy
    if(use_sudo_remote == 1)
        sprintf(buffer, "sudo -S ./%s eth0 %d %s %d &", proxy_filename, rport, inet_ntoa(mapped.sin_addr), htons(mapped.sin_port));
    else
        sprintf(buffer, "su -c \"./%s eth0 %d %s %d &\"", proxy_filename, rport, inet_ntoa(mapped.sin_addr), htons(mapped.sin_port));
    DEBUG_PRINT("Executing command via SSH: %s\n", buffer);
    if(ssh_channel_is_open(channel) && !ssh_channel_is_eof(channel))
    {
        ssh_channel_write(channel, buffer, strlen(buffer));
        ssh_channel_write(channel, "\n", 1);
    }
    char remote_host[128], tunip_string[128];
    memset(remote_host, 0, sizeof(remote_host));
    memset(tunip_string, 0, sizeof(tunip_string));
    int remote_port = 0;
    nbytes = ssh_channel_read(channel, buffer, sizeof(buffer), 0);
    while(nbytes > 0)
    {
        char *tunip = strstr(buffer, "TUNIP=");
        if(tunip)
        {
            tunip += strlen("TUNIP=");
            tunip_string[0] = '\0';
            strncat(tunip_string, tunip, strcspn(tunip, " "));
        }
        char *connect = strstr(buffer, "CONNECT=");
        if(connect)
        {
            connect += strlen("CONNECT=");
            strncat(remote_host, connect, strcspn(connect, "\r\n"));
            break;
        }
        /* if(write(STDOUT_FILENO, buffer, nbytes) != nbytes) */
        /* { */
        /*     fprintf(stderr, "Error reading command output from SSH: %s\n", */
        /*             ssh_get_error(my_ssh_session)); */
        /*     ssh_channel_close(channel); */
        /*     ssh_channel_free(channel); */
        /*     ssh_disconnect(my_ssh_session); */
        /*     ssh_free(my_ssh_session); */
        /*     exit(EXIT_FAILURE); */
        /* } */
        nbytes = ssh_channel_read(channel, buffer, sizeof(buffer), 0);
    }
    DEBUG_PRINT("Finished SSH session...\n");
    if(*remote_host)
    {
        DEBUG_PRINT("Proxy is listening at %s\n", remote_host);
        colon = strchr(remote_host, ':');
        if(colon)
        {
            *colon = '\0';
            remote_port = strtol(colon + 1, NULL, 10);
        }
    }
    else
    {
        fprintf(stderr, "Error: couldn't parse \"CONNECT=\" string from SSH session. Exiting.\n");
        ssh_channel_close(channel);
        ssh_channel_free(channel);
        ssh_disconnect(my_ssh_session);
        ssh_free(my_ssh_session);
        exit(EXIT_FAILURE);
    }

    ssh_channel_send_eof(channel);
    ssh_channel_close(channel);
    ssh_channel_free(channel);
    ssh_disconnect(my_ssh_session);
    ssh_free(my_ssh_session);

    DEBUG_PRINT("Sending \"OPEN!\" packet to remote host (for UDP hole punching)\n");
    hostinfo = gethostbyname(remote_host);
    if(!hostinfo) {
        fprintf(stderr, "Error resolving remote-host\n");
        exit(EXIT_FAILURE);
    }
    socklen_t slen = sizeof(struct sockaddr_in);
    memset(&udp_server_addr, 0, sizeof(udp_server_addr));
    udp_server_addr.sin_family = AF_INET;
    udp_server_addr.sin_addr = *(struct in_addr*) hostinfo->h_addr;
    udp_server_addr.sin_port = htons(remote_port);
    strcpy(buffer, "OPEN!");
    sendto(sock_udp, buffer, 5, 0,(struct sockaddr*)&udp_server_addr, slen);
    close(sock_udp); // free up port for later

    DEBUG_PRINT("Tunnel is established!\n");

    char socksaddress[32];
    sprintf(socksaddress, "127.0.0.1:%d", socksport);
    if(0 != tun2socks_init(tundevice, tunip_string, "255.255.255.255", socksaddress, tun_packet_received))
    {
        printf("tun2socks_init() failed\n");
        exit(EXIT_FAILURE);
    }

    tundevice = tun2socks_getifname();

    // start SSH SOCKS proxy
    pid_t sshpid = fork();
    if(sshpid < 0)
    {
        perror("fork failed");
        exit(EXIT_FAILURE);
    }
    if(sshpid == 0)
    {
        char sportS[10], socksportS[10];
        sprintf(sportS, "%d", sport);
        sprintf(socksportS, "%d", socksport);
        if(skeyfile)
        {
            execl("/usr/bin/ssh", "ssh", "-N", "-l", suser, "-p", sportS, "-D", socksportS, "-i", skeyfile, shost, (char *) 0);
        } else {
            execl("/usr/bin/ssh", "ssh", "-N", "-l", suser, "-p", sportS, "-D", socksportS, shost, (char *) 0);
        }
        printf("yoyo SSH finished\n");
        exit(0);
    }

    // bind UDP tunnel
    sock_udp_tun = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    setsockopt(sock_udp_tun, SOL_SOCKET, SO_BINDTODEVICE, iface_out, 4);

    struct sockaddr_in udp_tun_listen_addr, other_addr;
    udp_tun_listen_addr.sin_family = AF_INET;
    udp_tun_listen_addr.sin_addr.s_addr = INADDR_ANY;
    udp_tun_listen_addr.sin_port = mapped.sin_port;

    rc = bind(sock_udp_tun,(struct sockaddr *)&udp_tun_listen_addr, sizeof(udp_tun_listen_addr));

    pid_t child = fork();
    if(child < 0)
    {
        perror("fork failed");
        exit(EXIT_FAILURE);
    }
    if(child == 0)
    {
        // child process listening for packets from the UDP tunnel

        // clear sock_udp_tun buffer (should have some stun_request results)
        recvfrom(sock_udp_tun, (void *)buffer, BUFLEN, 0, (struct sockaddr *)&other_addr, &slen);
        while(1)
        {
            slen = sizeof(struct sockaddr_in);
            int recsize = recvfrom(sock_udp_tun, (void *)buffer, BUFLEN, 0, (struct sockaddr *)&other_addr, &slen);
            if(recsize > 0)
            {
                /* hexDump("packet from UDP tunnel", buffer, recsize); */
                tun2socks_write(buffer, recsize);
            }
        }
        exit(EXIT_SUCCESS);
    }

  /* pid_t nspid = fork();
    if(nspid < 0)
    {
        perror("fork failed");
        exit(EXIT_FAILURE);
    }
    if(nspid == 0)
    {
        unshare(CLONE_NEWNET|CLONE_NEWNS);
char cmd2[128];
sprintf(cmd2, "/sbin/ip netns add test");
        system(cmd2);
        // wait for TUN device
        do
        {
            printf("Waiting for TUN device...\n");
            sleep(1);
            sprintf(buffer, "/sbin/ip netns exec test ip link show %s >/dev/null 2>/dev/null", tundevice);
        } while(system(buffer) != 0);

        // bring up TUN device
        sprintf(buffer, "/sbin/ip netns exec test ip link set dev %s up", tundevice);
        system(buffer);
        
        // configure IP of tun device
        sprintf(buffer, "/sbin/ip netns exec test ip addr add %s/32 dev %s", tunip_string, tundevice);
        system(buffer);

        // configure default route
        sprintf(buffer, "/sbin/ip netns exec test ip route add default dev %s", tundevice);
        system(buffer);

        if(nameserver)
        {
            // bind-mount resolv.conf
            sprintf(buffer, "/bin/mount -o bind %s /etc/resolv.conf", resolv_filename);
            system(buffer);
        }

        if(argv[optind+1] == NULL)
        {
            char *shell = getenv("SHELL");
            if(shell) execvp(shell, NULL);
        }
        else
        {
            execvp(argv[optind+1], &argv[optind+1]);
        }
        exit(0);
    }*/

	char cmd[128];

	sprintf(cmd, "/sbin/ip link set %s netns tunnel", tundevice);
	system(cmd);

	//bring up TUN device
        sprintf(buffer, "/sbin/ip netns exec tunnel ip link set dev %s up", tundevice);
        system(buffer);

        // configure IP of tun device
        sprintf(buffer, "/sbin/ip netns exec tunnel ip addr add %s/32 dev %s", tunip_string, tundevice);
        system(buffer);

        // configure default route
        sprintf(buffer, "/sbin/ip netns exec tunnel ip route add default  via %s", tunip_string);
        system(buffer);

        /*if(nameserver)
        {
            // bind-mount resolv.conf
            sprintf(buffer, "/bin/mount -o bind %s /etc/resolv.conf", resolv_filename);
            system(buffer);
        }*/
 
    tun2socks_run();

    slen = sizeof(struct sockaddr_in);
    sendto(sock_udp_tun, "EXIT", 4, 0,(struct sockaddr*)&udp_server_addr, slen);

    kill(child, SIGKILL);
    kill(sshpid, SIGKILL);

    system(buffer);	 
    if(nameserver) unlink(resolv_filename);

    // TODO:
    // - periodically send keepalive packets through tundevice

    return 0;
}
