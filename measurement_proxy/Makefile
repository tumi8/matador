CC=gcc
CCFLAGS+=-Wall -I. -Wno-pointer-sign -fomit-frame-pointer
LIBS=-lssh

ifndef DIET
ifneq (,$(shell which diet))
DIET=yes
endif
endif

ifeq ($(DIET), yes)
ifeq (,$(shell which diet))
$(error diet not found in path $(PATH))
endif
SCC=diet gcc
else
SCC=gcc
endif

ifeq ($(DEBUG), yes)
CCFLAGS += -g
LDFLAGS += -O0
else
CCFLAGS += -s -DNDEBUG
LDFLAGS += -O2
endif

BIT=$(shell getconf LONG_BIT)

all: tunnel proxy

debug:
	$(eval DEBUG=yes)

diet:
	$(eval DIET=yes)

fat:
	$(eval DIET=no)

singlearch: tunnel
	make DEBUG=$(DEBUG) DIET=$(DIET) proxy-$(BIT)
	ln -f proxy-$(BIT) proxy

tunnel: tunnel.c ministun.c tools.c tools.h
	make DEBUG=$(DEBUG) DIET=$(DIET) tunnel-bin

proxy: proxy.c bind_public.c ministun.c tools.c tools.h
ifneq ($(BIT), 32)
	make DEBUG=$(DEBUG) DIET=$(DIET) proxy-64
endif
	make DEBUG=$(DEBUG) DIET=$(DIET) proxy-32
	ln -f proxy-$(BIT) proxy

proxy-64: build-64/proxy.o build-64/bind_public.o build-64/tools.o build-64/ministun.o
	$(SCC) -static $(CCFLAGS) $(LDFLAGS) build-64/proxy.o build-64/bind_public.o build-64/tools.o build-64/ministun.o -o proxy-64

proxy-32: build-32/proxy.o build-32/bind_public.o build-32/tools.o build-32/ministun.o
	$(SCC) -static $(CCFLAGS) $(LDFLAGS) -m32 build-32/proxy.o build-32/bind_public.o build-32/tools.o build-32/ministun.o -o proxy-32

tunnel-bin: build-$(BIT)/tunnel.o build-$(BIT)/tools.o build-$(BIT)/ministun.o tun2socks/tun2socks.a
	$(CC) $(CCFLAGS) build-$(BIT)/tunnel.o tun2socks/tun2socks.a build-$(BIT)/tools.o build-$(BIT)/ministun.o -o tunnel $(LIBS)

tun2socks/tun2socks.a:
	make -C tun2socks

build-%:
	mkdir -p $@

build-64/%.o: %.c | build-64
	$(CC) $(CCFLAGS) -c -o $@ $<

build-32/%.o: %.c | build-32
	$(CC) $(CCFLAGS) -m32 -c -o $@ $<

clean:
	make -C tun2socks clean
	rm -rf build-32 build-64 proxy-32 proxy-64 proxy tunnel

