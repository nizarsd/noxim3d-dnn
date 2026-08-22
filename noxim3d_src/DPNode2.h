#ifndef __DPNODE_H__
#define __DPNODE_H__
//---------------------------------------------------------------------------
#include "systemc.h"
#include "NoximDefs.h"

SC_MODULE(DPNode)    
{
  
 // I/O Ports
   sc_in<bool>         dp_clock, reset;        	 
   sc_in<int>          dp_rx[DIRECTIONS]; 		  			// DP-network input 
  // sc_in<int>        used_buffer_size[DIRECTIONS];      // cost function 
   sc_in<int>          current_router_temp; 				     // cost function     	 

   sc_out<int>         dp_tx[DIRECTIONS];                // DP-network output           
   sc_out<int>         dp_dir[DIRECTIONS];       	 // DP-network selected direction

 // Registers

  int                local_id, dst_id;                           // Unique ID

 // Functions

 void dpProcess();
 void configure( const int _local_id) ;

 // Constructor

  SC_CTOR(DPNode)
  {
    SC_METHOD(dpProcess);
     sensitive <<reset    <<dp_clock.pos();
	 sensitive <<dp_rx[0] <<dp_rx[1] <<dp_rx[2] <<dp_rx[3] <<dp_rx[4] << dp_rx[5];
	 sensitive <<current_router_temp ; 
	 //used_buffer_size[0] <<used_buffer_size[1]<< used_buffer_size[2]<< used_buffer_size[3]<< used_buffer_size[4]<< used_buffer_size[5];

  }

};
#endif


