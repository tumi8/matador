/*
 * Copyright 2013 The Trustees of Princeton University
 * All Rights Reserved
 * 
 * Re-map bind() on 0.0.0.0 or :: to bind() on the node's public IP address
 * Jude Nelson (jcnelson@cs.princeton.edu)
 */

#include <stdio.h>
#include <stdlib.h>
#include <memory.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <limits.h>
#include <errno.h>
#include <netdb.h>
#include <unistd.h>
#include <netinet/in.h>
#include <sys/stat.h>

int get_public_ip( struct sockaddr* addr ) {

   int rc = 0;

   struct addrinfo hints;
   memset( &hints, 0, sizeof(hints) );
   hints.ai_family = addr->sa_family;
   hints.ai_flags = AI_CANONNAME;
   hints.ai_protocol = 0;
   hints.ai_canonname = NULL;
   hints.ai_addr = NULL;
   hints.ai_next = NULL;

   rc = 0;

   // get the node hostname
   struct addrinfo *result = NULL;
   char hostname[HOST_NAME_MAX+1];
   gethostname( hostname, HOST_NAME_MAX );

   // get the address information from the hostname
   rc = getaddrinfo( hostname, NULL, &hints, &result );
   if( rc != 0 ) {
	  // could not get addr info
	  fprintf(stderr, "bind_public: get_public_ip: getaddrinfo: %s\n", gai_strerror( rc ) );
	  errno = EINVAL;
	  return -errno;
   }

   // NOTE: there should only be one IP address for this node, but it
   // is possible that it can have more.  Here, we just take the first
   // address given.

   switch( addr->sa_family ) {
	  case AF_INET:
		 // IPv4
		 ((struct sockaddr_in*)addr)->sin_addr = ((struct sockaddr_in*)result->ai_addr)->sin_addr;
		 break;

	  case AF_INET6:
		 // IPv6
		 ((struct sockaddr_in6*)addr)->sin6_addr = ((struct sockaddr_in6*)result->ai_addr)->sin6_addr;
		 break;

	  default:
		 fprintf(stderr, "bind_public: get_public_ip: unknown socket address family %d\n", addr->sa_family );
		 rc = -1;
		 break;
   }

   freeaddrinfo( result );

   return rc;
}


// is a particular sockaddr initialized to 0.0.0.0 or ::?
int is_addr_any( const struct sockaddr* addr ) {
   int ret = 0;

   switch( addr->sa_family ) {
	  case AF_INET: {
		 // IPv4
		 struct sockaddr_in* addr4 = (struct sockaddr_in*)addr;
		 if( addr4->sin_addr.s_addr == INADDR_ANY )
			ret = 1;    // this is 0.0.0.0
		 break;
	  }
	  case AF_INET6: {
		 // IPv6
		 struct sockaddr_in6* addr6 = (struct sockaddr_in6*)addr;
		 if( memcmp( &addr6->sin6_addr, &in6addr_any, sizeof(in6addr_any) ) == 0 )
			ret = 1;    // this is ::
		 break;
	  }
	  default:
		 // unsupported bind
		 fprintf(stderr, "bind_public: is_addr_any: unsupported socket address family %d\n", addr->sa_family );
		 ret = -1;
		 break;
   }

   return ret;
}


void print_ip4( uint32_t i ) {
   i = htonl( i );
   printf("%i.%i.%i.%i",
		  (i >> 24) & 0xFF,
		  (i >> 16) & 0xFF,
		  (i >> 8) & 0xFF,
		  i & 0xFF);
}

void print_ip6( uint8_t* bytes ) {
   printf("%x:%x:%x:%x:%x:%x:%x:%x:%x:%x:%x:%x:%x:%x:%x:%x",
		  bytes[0], bytes[1], bytes[2], bytes[3],
		  bytes[4], bytes[5], bytes[6],  bytes[7],
		  bytes[8],  bytes[9],  bytes[10],  bytes[11],
		  bytes[12],  bytes[13],  bytes[14],  bytes[15] );
}

void debug( const struct sockaddr* before, struct sockaddr* after ) {
   printf("bind_public: ");
   switch( before->sa_family ) {
	  case AF_INET:
		 print_ip4( ((struct sockaddr_in*)before)->sin_addr.s_addr );
		 printf(" --> ");
		 print_ip4( ((struct sockaddr_in*)after)->sin_addr.s_addr );
		 printf("\n");
		 break;
	  case AF_INET6:
		 print_ip6( ((struct sockaddr_in6*)before)->sin6_addr.s6_addr );
		 printf(" --> " );
		 print_ip6( ((struct sockaddr_in6*)after)->sin6_addr.s6_addr );
		 printf("\n");
		 break;
	  default:
		 printf("UNKNOWN --> UNKNOWN\n");
		 break;
   }
   fflush( stdout );
}

// if the caller attempted to bind to 0.0.0.0 or ::, then change it to
// this node's public IP address
int bind_public(int sockfd, const struct sockaddr *addr, socklen_t addrlen) {

   errno = 0;

   int tried_normal_bind = 0;

   int rc = is_addr_any( addr );

   fprintf( stderr, "bind(%d, %p, %ld)\n", sockfd, addr, addrlen);

   if( rc > 0 ) {

	  rc = 0;

	  // rewrite this address
	  struct sockaddr_storage new_addr;
	  memset( &new_addr, 0, sizeof(struct sockaddr_storage));
	  memcpy( &new_addr, addr, addrlen );

	  rc = get_public_ip( (struct sockaddr*)&new_addr );
	  if( rc == -EINVAL ) {
		 // this will happen for DHCP, so bind the normal way
		 fprintf(stderr, "WARNING: could not get IP address; attempting normal bind.");
		 rc = bind( sockfd, (struct sockaddr*)&new_addr, addrlen );
		 fprintf(stderr, "normal bind rc = %d, errno = %d\n", rc, errno );
		 tried_normal_bind = 1;
	  }
	  else if( rc != 0 ) {
		 rc = -1;
	  }

	  if( rc == 0 && tried_normal_bind == 0 ) {
		 debug( addr, (struct sockaddr*)&new_addr );
		 rc = bind( sockfd, (struct sockaddr*)&new_addr, addrlen );
		 fprintf( stderr, "re-addressed bind rc = %d, errno = %d\n", rc, errno);
	  }
   }
   else {
	  rc = bind( sockfd, (struct sockaddr*)addr, addrlen );
	  fprintf( stderr, "bind rc = %d, errno = %d\n", rc, errno);
   }
   return rc;
}
