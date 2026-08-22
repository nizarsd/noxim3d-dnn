/*****************************************************************************

  TRouter.h -- Router definition

 *****************************************************************************/
/* Copyright 2005-2007  
    Fabrizio Fazzino <fabrizio.fazzino@diit.unict.it>
    Maurizio Palesi <mpalesi@diit.unict.it>
    Davide Patti <dpatti@diit.unict.it>

 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
 */
#ifndef __TROUTER_H__
#define __TROUTER_H__

//---------------------------------------------------------------------------

#include <systemc.h>
#include "NoximDefs.h"
#include "TBuffer.h"
#include "TStats.h"
#include "TGlobalRoutingTable.h"
#include "TLocalRoutingTable.h"
#include "TReservationTable.h"


extern unsigned int drained_volume;

SC_MODULE(TRouter)
{

  // I/O Ports
  sc_in_clk          clock;        // The input clock for the router
  sc_in<bool>        reset;        // The reset signal for the router

  sc_in<TFlit>       flit_rx[DIRECTIONS+1];   // The input channels (including local one)
  sc_in<bool>        req_rx[DIRECTIONS+1];    // The requests associated with the input channels
  sc_out<bool>       ack_rx[DIRECTIONS+1];    // The outgoing ack signals associated with the input channels

  sc_out<TFlit>      flit_tx[DIRECTIONS+1];   // The output channels (including local one)
  sc_out<bool>       req_tx[DIRECTIONS+1];    // The requests associated with the output channels
  sc_in<bool>        ack_tx[DIRECTIONS+1];    // The outgoing ack signals associated with the output channels

  sc_out<int>       free_slots[DIRECTIONS+1];
  sc_in<int>        free_slots_neighbor[DIRECTIONS+1];

  sc_out<int>       Rthrot_level;  // output of the throttling level to PE (to reduce the injuction rate of packets) <Nizar>

  // Neighbor-on-Path related I/O

  sc_out<TNoP_data>       NoP_data_out[DIRECTIONS];
  sc_in<TNoP_data>        NoP_data_in[DIRECTIONS];
  
    // DP-network  --- by Ra'ed ***************
  
 //sc_in <int>        dp_cost; 
   sc_in <int>        dp_dir[DIRECTIONS]; 
  // sc_out<int>      used_buffer_size[DIRECTIONS]; 
   sc_out<int>        local_dp_cost[DIRECTIONS]; 
   

  // Registers

  int                local_id;                              // Unique ID
  int                routing_type;                    // Type of routing algorithm
  int                selection_type;
  TBuffer            buffer[DIRECTIONS+1];            // Buffer for each input channel 
  bool               current_level_rx[DIRECTIONS+1];  // Current level for Alternating Bit Protocol (ABP)
  bool               current_level_tx[DIRECTIONS+1];  // Current level for Alternating Bit Protocol (ABP)
  TStats             stats;                           // Statistics
  TLocalRoutingTable routing_table;                          // Routing table
  TReservationTable  reservation_table;                       // Switch reservation table
  unsigned int       start_from_port;                 // Port from which to start the reservation cycle
  unsigned long      routed_flits;
  

 // Functions
  void               rxProcess();        // The receiving process
  void               txProcess();        // The transmitting process
  void               bufferMonitor();
  void               routing_directionsUpdater();  // to update the routing direction inside the router
  void               configure( const int _id, const double _warm_up_time,
			                          const unsigned int _max_buffer_size,
			                          TGlobalRoutingTable& grt);

  unsigned long getRoutedFlits(); // Returns the number of routed flits 

  unsigned int  getFlitsCount();  // Returns the number of flits into the router
  
  

  double        getPower();  			// Returns the total power dissipated by the router
  double        getPower_aborted_flits();	// Returns the wasted power dissipated by aborted flits in each router
  
 
  // Constructor

  SC_CTOR(TRouter)
  {
    SC_METHOD(rxProcess);
    sensitive << reset;
    sensitive << clock.pos();

    SC_METHOD(txProcess);
    sensitive << reset;
    sensitive << clock.pos();

    SC_METHOD(bufferMonitor);
    sensitive << reset;
    sensitive << clock.pos();

    SC_METHOD(cost_to_go);
    sensitive << reset;
    sensitive << clock.pos();
    
    SC_METHOD(routing_directionsUpdater);
    sensitive << reset; 
	sensitive << clock.pos();
    //sensitive <<dp_dir[0] <<dp_dir[1] <<dp_dir[2] <<dp_dir[3] <<dp_dir[4] << dp_dir[5];
  }

 private:

  // performs actual routing + selection
  int route(const TRouteData& route_data);

  // wrappers
  int selectionFunction(const vector<int>& directions,const TRouteData& route_data);
  vector<int> routingFunction(const TRouteData& route_data);




  // selection strategies
  int selectionRandom(const vector<int>& directions);
  int selectionBufferLevel(const vector<int>& directions);
  int selectionNoP(const vector<int>& directions,const TRouteData& route_data);
  int selectionDP(const vector<int>& directions,const TRouteData& route_data);

  // routing functions
  vector<int> routingXY(const TCoord& current, const TCoord& destination);
  vector<int> routingWestFirst(const TCoord& current, const TCoord& destination);
  vector<int> routingNorthLast(const TCoord& current, const TCoord& destination);
  vector<int> routingNegativeFirst(const TCoord& current, const TCoord& destination);
  vector<int> routingNegativeFirst3D(const TCoord& current, const TCoord& destination);
  vector<int> routingOddEven(const TCoord& current, const TCoord& source, const TCoord& destination);
  vector<int> routingBalancedOddEven(const TCoord& current, const TCoord& source, const TCoord& destination);
  vector<int> routingDyAD(const TCoord& current, const TCoord& source, const TCoord& destination);
  vector<int> routingLookAhead(const TCoord& current, const TCoord& destination);
  vector<int> routingFullyAdaptive(const TCoord& current, const TCoord& destination);
  vector<int> routingTableBased(const int dir_in, const TCoord& current, const TCoord& destination);
 // added by Ra'ed
  vector<int> routingXYZ(const TCoord& current, const TCoord& destination);
  vector<int> routingFullyAdaptive3D(const TCoord& current, const TCoord& destination);
  //vector<int> routingNegativeFirstNM(const TRouteData& route_data);
  //vector<int> routingNegativeFirstNM3D(const TRouteData& route_data);
  vector<int> routingDW_XYZ(const TCoord& current, const TCoord& destination, const int dw);
 
  // <Nizar>
  vector<int> routingDwOddEven(const TRouteData& route_data);
  vector<int> routingOddEven3D(const TRouteData& route_data);
  vector<int> routingOddEven3DNM(const TRouteData& route_data);
  vector<int> routingOddEvenBalanced(const TRouteData& route_data);

  vector<int>  directionsByBufferLevel(const vector<int>& directions);

  vector<int> routingOddEven0(const TCoord& current,const TCoord& source, const TCoord& destination);
  vector<int> routingOddEven1(const TCoord& current, const TCoord& source, const TCoord& destination);

  vector<int> routingOddEvenNM(const TCoord& current, const TCoord& source, const TCoord& destination, const int dir_in);
  vector<int> routingOddEvenNM0(const TCoord& current, const TCoord& source, const TCoord& destination, const int dir_in);
  vector<int> routingOddEvenNM1(const TCoord& current, const TCoord& source, const TCoord& destination, const int dir_in);
  
  TNoP_data getCurrentNoPData() const;
  void NoP_report() const;
  int NoPScore(const TNoP_data& nop_data, const vector<int>& nop_channels) const;
  int reflexDirection(int direction) const;
  int getNeighborId(int _id,int direction) const;
  bool inCongestion();
  void cost_to_go();
  int routing_directions[DPSIZE][DIRECTIONS]; // added by Ra'ed

 public:
   unsigned int local_drained;
   float router_temp; // added by Ra'ed
   int   dw_level;
   int traffic_counter;
   int rx_flit_counter;   // per-router received-flit count; binned/dumped by TNoC::dumpTraffic (CLI: -trafficbin)
   
	// was: int traffic_counter; <Nizar 2026)
	int    channel_load[DIRECTIONS];      // accumulated occupancy per output channel
	int    channel_samples;               // sample count in current window
	int    flits_sent[DIRECTIONS];        // flits actually forwarded per output channel
	                                      // in the current window = lambda for Little's Law
	long   flits_total[DIRECTIONS];       // same, but NEVER reset -- for DPTRACE only, so
	                                      // per-cycle departures can be recovered by diffing
	int    dp_channel_cost[DIRECTIONS];   // averaged per-channel cost, published to DP
	int    dp_cost_ewma[DIRECTIONS];      // EWMA state for dp_channel_cost, Q8 fixed point
	                                      // (x256) so the blend can decay below 1%; only
	                                      // used when env DPDECAY is set, see cost_to_go()


   //<Nizar>
   float pre_temp; 
   int tindex;  
   float throt_level;  // the current throttling level of the router (0,1)
   int clk_multiple;    
};

#endif
