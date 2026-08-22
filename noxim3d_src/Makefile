TARGET_ARCH = linux64
CC     = g++
OPT    = -O3 -march=native
DEBUG  = -g
OTHER  = -Wall -Wno-deprecated -std=c++14
CFLAGS = $(OPT) $(OTHER)
#CFLAGS = $(DEBUG) $(OPT) $(OTHER)

MODULE = noxim
SRCS = TNoC.cpp TRouter.cpp TProcessingElement.cpp TBuffer.cpp TStats.cpp DPNode.cpp \
	TGlobalStats.cpp TGlobalRoutingTable.cpp TLocalRoutingTable.cpp \
	TGlobalTrafficTable.cpp TReservationTable.cpp TPower.cpp \
        CmdLineParser.cpp main.cpp
OBJS = $(SRCS:.cpp=.o)

include ./Makefile.defs
