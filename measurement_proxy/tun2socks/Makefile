AR=ar
CC=gcc
#CCFLAGS+=-Wall -I. -Wno-pointer-sign -fomit-frame-pointer -std=gnu99
CCFLAGS+=-I. -Wno-pointer-sign -fomit-frame-pointer -std=gnu99
INCLUDES=-I. -Ilwip/src/include/ipv4 -Ilwip/src/include/ipv6 -Ilwip/src/include -Ilwip/custom
DEFS=-DBADVPN_THREAD_SAFE=0 -DBADVPN_LINUX -DBADVPN_BREACTOR_BADVPN -D_GNU_SOURCE -DBADVPN_USE_SIGNALFD -DBADVPN_USE_EPOLL -DBADVPN_LITTLE_ENDIAN

TARGET = tun2socks.a

OBJECTS = $(patsubst %.c, %.o, $(shell find . -name "*.c"))

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(AR) rvs $(TARGET) $(OBJECTS)

%.o: %.c
	$(CC) -c $(CCFLAGS) $(INCLUDES) $(DEFS) $^ -o $@

clean:
	rm -f $(TARGET) $(OBJECTS)

