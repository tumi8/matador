#ifndef TOOLS_H
#define TOOLS_H

#define MAXPORT 65535

#define DEFAULT_INTERFACE "eth0"
#define DEFAULT_TUNDEVICE NULL
#define DEFAULT_SOCKSPORT 8880
#define DEFAULT_NAMESERVER "8.8.8.8"

extern void hexDump (char *desc, void *addr, int len);

#ifdef NDEBUG
#define DEBUG_PRINT(...) do {} while (0)
#else
#define DEBUG_PRINT(...) printf(__VA_ARGS__)
#endif

#endif
