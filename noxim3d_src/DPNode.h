#ifndef __DPNODE_H__
#define __DPNODE_H__
//---------------------------------------------------------------------------
#include "systemc.h"
#include "NoximDefs.h"

SC_MODULE(DPNode)    
{
  
 // I/O Ports
   sc_in<bool>         dp_clock, reset;        	 
   sc_in<int>          dp_rx[DIRECTIONS]; 		  		   // DP-network input 
  // sc_in<int>        used_buffer_size[DIRECTIONS];       // cost function 
   sc_in<int>          local_dp_cost[DIRECTIONS]; 			   // cost function     	 

   sc_out<int>         dp_tx[DIRECTIONS];                // DP-network output           
   sc_out<int>         dp_dir[DIRECTIONS];       	 // DP-network selected direction
   //sc_out<int>         dp_dir_cost[DIRECTIONS];       	 // DP-network direction costs (LATER !)
	

 // Registers

  int local_id, dst_id;               // Unique ID
  int frozen_local_cost[DIRECTIONS];  // to latch the cost to DP nodes once for every full convergence of DP
  int stime2;
  int cost_mem[DPSIZE][DIRECTIONS];   // advertised cost per dst per input dir

  // Turn-legality cache: can_turn() is invariant over a run (depends only on
  // node coords, dst, and the fixed routing algorithm), so memoize it per
  // destination to keep it off the per-cycle hot path.
  bool legal_cache[DPSIZE][DIRECTIONS][DIRECTIONS];
  bool legal_cached[DPSIZE];
 // Functions

 void dpProcess();
 void configure( const int _local_id) ;

// Routing functions <Nizar>
 bool can_turn(int dir_in, int dir_out, int dest);
 bool can_turnOddEven(int dir_in, int dir_out, int dst_id);
 bool can_turnOddEvenNM(int dir_in, int dir_out, int dst_id);
 bool can_turnNegativeFirst(int dir_in, int dir_out, int dst_id);
 bool can_turnOddEvenBalanced(int dir_in, int dir_out, int dst_id);
 bool can_turnFullyAdaptive(int dir_in, int dir_out, int dst_id);

 bool isMinimalDirection(int dir,
							const TCoord& current,
							const TCoord& destination,
							bool incoming);
	vector<int> routingOddEvenDPStrict(const TCoord& current,
								   const TCoord& destination);

	vector<int> routingOddEven0_DPStrict(const TCoord& current,
									 const TCoord& destination);

	vector<int> routingOddEven1_DPStrict(const TCoord& current,
									 const TCoord& destination);
									 

 vector<int> routingOddEven(const TCoord& current, const TCoord& source, const TCoord& destination);
 
 vector<int> routingOddEven0(const TCoord& current, const TCoord& source, const TCoord& destination);
 vector<int> routingOddEven1(const TCoord& current, const TCoord& source, const TCoord& destination);

 vector<int> routingXYZ(const TCoord& current, const TCoord& destination);
 bool can_turnDwOddEven(int dir_in, int dir_out, int dst_id);
 vector<int> routingOddEvenNM(const TCoord& current, const TCoord& source, const TCoord& destination, const int dir_in); // Nonminumum Odd_Even
 vector<int> routingOddEvenNM0(const TCoord& current, const TCoord& source, const TCoord& destination, const int dir_in); // Odd_even (row)
 vector<int> routingOddEvenNM1(const TCoord& current, const TCoord& source, const TCoord& destination, const int dir_in); // Even_Odd
 
 // Constructor

  SC_CTOR(DPNode)
  {
    SC_METHOD(dpProcess);
     sensitive <<reset    <<dp_clock.pos();
	 // sensitive <<dp_rx[0] <<dp_rx[1] <<dp_rx[2] <<dp_rx[3] <<dp_rx[4] << dp_rx[5];
	 // sensitive <<local_dp_cost ; 
	 //used_buffer_size[0] <<used_buffer_size[1]<< used_buffer_size[2]<< used_buffer_size[3]<< used_buffer_size[4]<< used_buffer_size[5];

  }

};
#endif


