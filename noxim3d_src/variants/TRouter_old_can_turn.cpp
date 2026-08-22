/*****************************************************************************

  TRouter.cpp -- Router implementation

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
#include "TRouter.h"

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------


void TRouter::rxProcess()
{
bool actvity_flag=0;

  if(reset.read())
    {
      // Clear outputs and indexes of receiving protocol
      for(int i=0; i<DIRECTIONS+1; i++)
	{
	  ack_rx[i].write(0);
	  current_level_rx[i] = 0;
	}
      reservation_table.clear();
      routed_flits = 0;
      local_drained = 0;
      //stats.ClearCommHist();
    }

  else if (clock.posedge())
    {
      // For each channel decide if a new flit can be accepted
      //
      // This process simply sees a flow of incoming flits. All arbitration
      // and wormhole related issues are addressed in the txProcess()
 
      for(int i=0; i<DIRECTIONS+1; i++)
	{
	  // To accept a new flit, the following conditions must match:
	  //
	  // 1) there is an incoming request
	  // 2) there is a free slot in the input buffer of direction i

	  if ( (req_rx[i].read()==1-current_level_rx[i]) && !buffer[i].IsFull() )
	    {
	      TFlit received_flit = flit_rx[i].read();
	      
	      //if (received_flit.flit_type != FLIT_TYPE_HEAD || buffer[i].IsEmpty()) // not accepting a head flit without be sure that the buffer is empty 
	      {
		 if(TGlobalParams::verbose_mode > VERBOSE_OFF )
		   {
		     cout << sc_time_stamp().to_double()/1000 << ": Router[" << local_id <<"], Input[" << i << "], Received flit: " << received_flit << endl;
		   }

		// Store the incoming flit in the circular buffer
		buffer[i].Push(received_flit);  
		actvity_flag=1;
		//free_slots[i] = buffer[i].getCurrentFreeSlots();          

		// Negate the old value for Alternating Bit Protocol (ABP)
		current_level_rx[i] = 1-current_level_rx[i];

		// Incoming flit
		// traffic_counter++;
		stats.power.Incoming();
	      }
	    }
	  ack_rx[i].write(current_level_rx[i]);
	}
    }
  
    if ( actvity_flag==0)
	 stats.power.Standby();

}

//---------------------------------------------------------------------------

void TRouter::txProcess()
{
bool actvity_flag=0;

  if (reset.read())
   {
      // Clear outputs and indexes of transmitting protocol
      for(int i=0; i<DIRECTIONS+1; i++)
	{
	  req_tx[i].write(0);
	  current_level_tx[i] = 0;
	   //if (i < DIRECTIONS)
	    //  used_buffer_size[i].write(1);    // Initilize the cost function of DP
	}
	router_temp=25.0;   // INITIAL ROUTER TEMP
	traffic_counter=0;  // for dw routing 
	dw_level=0;
	throt_level=1;	 // initial throttling level	
	tindex=0;  // Throttling level index (in dyTemp()
	Rthrot_level.write(100);
		
   }
   else if (clock.posedge())
   { 
    int clk2=int(sc_time_stamp().to_double()/1000-DEFAULT_RESET_TIME); // Nizar
    int clk_multiple=10;
    int Vclk_multiple=1;
    bool dwFlag=(TGlobalParams::routing_algorithm==ROUTING_DW_XYZ);		
    int op_throt_level=(int) (throt_level*100);
    Rthrot_level.write	(op_throt_level);  // throttling level of the PE is taken from the router

   	
	if(TGlobalParams::dy_t_mode > 0) // if thermal modelling is enabled <Nizar>
		clk_multiple=int (throt_level*10);
	 
	if  (((clk2%10) < clk_multiple ) || (((clk2%10) < Vclk_multiple)&& dwFlag)) 
			stats.power.Clocking();  // add clock power
      
  		
   	  
     // 1st phase: Reservation     
    for(int j=0; j<DIRECTIONS+1; j++)
	{       
	  int i = (start_from_port + j) % (DIRECTIONS + 1);
	  if ( !buffer[i].IsEmpty() )
	  {	      
	  	TFlit flit = buffer[i].Front();
	 	if (flit.flit_type==FLIT_TYPE_HEAD) 
		{
		  // prepare data for routing
		  TRouteData route_data;
		  route_data.current_id = local_id;
		  route_data.src_id = flit.src_id;    
		  route_data.dst_id = flit.dst_id;
		  route_data.dir_in = i;
		  route_data.dw	    = flit.dw;
		  actvity_flag=1;  // to check if we need to add standby power

		  int o = route(route_data);
		         
	bool vflag=(o==DIRECTION_UP || o==DIRECTION_DOWN || o==DIRECTION_LOCAL) && dwFlag;

	// add routing power accrording to throttling level (Vclk_multiple is for DW_ROUTING)
	 if  (((clk2%10) < clk_multiple ) || (((clk2%10) < Vclk_multiple)&& dwFlag)) 
			stats.power.Routing();
    			
  
     if  (((clk2%10) < clk_multiple ) || ((clk2%10) < Vclk_multiple) && vflag)   // clk_multiple is the throtted clock (0: max throttling, 10: no throttling)
        { 
	        
		
//	  if (TGlobalParams::routing_algorithm!=ROUTING_DW_XYZ)
//			stats.power.Routing();
          
    	  if(TGlobalParams::verbose_mode > VERBOSE_OFF )
    		cout << sc_time_stamp().to_double()/1000 
			       << ": Router[" << local_id 
			       << "], Input[" << i << "] (" << buffer[i].Size() << " flits)" 
			       << ", requested Output[" << o << "], flit: " << flit <<"  free slots neighbor =" << free_slots_neighbor[o] << endl;			

		  if (reservation_table.isAvailable(o) ) 
		    {
		      reservation_table.reserve(i, o);   
		      if(TGlobalParams::verbose_mode > VERBOSE_OFF )
			  	cout << sc_time_stamp().to_double()/1000
			       << ": Router[" << local_id 
			       << "], Input[" << i << "] (" << buffer[i].Size() << " flits)" 
			       << ", reserved Output[" << o << "], flit: " << flit << endl;
	      
           }         	
	   } // reservation throttling
  	  } // flit type head
    } // buffer not empty
  } // reservation directions
    
start_from_port++;

    // 2nd phase: Forwarding

   for(int i=0; i<DIRECTIONS+1; i++)
	{
	  if ( !buffer[i].IsEmpty() )
	    {
	      TFlit flit = buffer[i].Front();
	      int o = reservation_table.getOutputPort(i);
    bool vflag=(o==DIRECTION_UP || o==DIRECTION_DOWN || o==DIRECTION_LOCAL) && (TGlobalParams::routing_algorithm==ROUTING_DW_XYZ) ;
    if  (((clk2%10) < clk_multiple ) || ((clk2%10) < Vclk_multiple) && vflag)  
	 { 
	   if (o != NOT_RESERVED )
		{
		 if (current_level_tx[o] == ack_tx[o].read())
		  {
		     if(TGlobalParams::verbose_mode > VERBOSE_OFF )
			  cout << sc_time_stamp().to_double()/1000
			       << ": Router[" << local_id 
			       << "], Input[" << i << "] forward to Output[" << o << "], flit: " << flit << endl;

		      flit.hop_no++;
		      if (o == DIRECTION_DOWN)  // update the DW times the flit suffer
		      	flit.dw ++;
		      else
		      	flit.dw = 0;
		      	
		      //traffic_counter++;
		      flit_tx[o].write(flit);
		      current_level_tx[o] = 1 - current_level_tx[o];
		      req_tx[o].write(current_level_tx[o]);
		      buffer[i].Pop();
			  actvity_flag=1;

		      //free_slots[i] = buffer[i].getCurrentFreeSlots();
       		  // Add link traversal energy <Nizar>
			
		      if ((o==DIRECTION_UP) || (o==DIRECTION_DOWN)) 
				 stats.power.Vlink();
		      else 
				 {stats.power.Link(); stats.power.Forward();}
				 
				 
		      if (flit.flit_type == FLIT_TYPE_TAIL ) 
					reservation_table.release(o);

		      // Update stats
		      if (o == DIRECTION_LOCAL)
			  {
			  stats.receivedFlit(sc_time_stamp().to_double()/1000, flit);
			  if (TGlobalParams::max_volume_to_be_drained)
			    {
			      if (drained_volume >= TGlobalParams::max_volume_to_be_drained)
				sc_stop();
			      else
			      {
				drained_volume++;
				local_drained++;

			      }
			    }
			 }
		      else if (i != DIRECTION_LOCAL)
			{
			  // Increment routed flits counter
			  routed_flits++;

			}
		  } // handshake protocol
		}  // reserved
	  } // forward throttling
    } // buffer not empty
   } // forwarding directions 
      
} // else 
if ( actvity_flag==0)
	  stats.power.Standby();
}

//---------------------------------------------------------------------------

TNoP_data TRouter::getCurrentNoPData() const 
{
    TNoP_data NoP_data;

    for (int j=0; j<DIRECTIONS; j++)
    {
	NoP_data.channel_status_neighbor[j].free_slots = free_slots_neighbor[j].read();
	NoP_data.channel_status_neighbor[j].available = (reservation_table.isAvailable(j));
    }

    NoP_data.sender_id = local_id;

    return NoP_data;
}

//---------------------------------------------------------------------------

void TRouter::bufferMonitor()
{

 // for resetting performance counter every tcu time window <Nizar>
 int stime = (int) (sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);

  if (reset.read())
  {
	for (int i=0; i<DIRECTIONS+1; i++) free_slots[i].write(buffer[i].GetMaxBufferSize());
    for (int d=0; d<DIRECTIONS; d++) channel_load[d] = 0;
    channel_samples = 0;
  }
  else
  {				

	int maxb = TGlobalParams::buffer_depth ; // max buffer size

	  
	// accumulate downstream occupancy per output channel for DP with per channel cost, avg buffer level <Nizar> 
	for (int d = 0; d < DIRECTIONS; d++) {
		int free = free_slots_neighbor[d].read();
		if (free == NOT_VALID) continue;              // no neighbour (boundary) — skip, don't count
		if (free > maxb) free = maxb;
		channel_load[d] += (maxb - free);
	}
	channel_samples++;


  //  if (TGlobalParams::selection_strategy==SEL_BUFFER_LEVEL ||
	//TGlobalParams::selection_strategy==SEL_NOP)
   // {

      // update current input buffers level to neighbors
      for (int i=0; i<DIRECTIONS+1; i++)
		free_slots[i].write(buffer[i].getCurrentFreeSlots());

      // NoP selection: send neighbor info to each direction 'i'
      TNoP_data current_NoP_data = getCurrentNoPData();

      for (int i=0; i<DIRECTIONS; i++)
	NoP_data_out[i].write(current_NoP_data);
  //  }
  }

}

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

void TRouter::routing_directionsUpdater()
{
	if (TGlobalParams::selection_strategy != SEL_DP) return;

	int no_dst = TGlobalParams::mesh_dim_x*TGlobalParams::mesh_dim_y*TGlobalParams::mesh_dim_z;

	if (reset.read())
	{
		for (int i=0; i<no_dst; i++)
			for (int j=0; j<DIRECTIONS; j++)
				routing_directions[i][j] = -2;
		return;
	}

	int stime = (int)(sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);
	int phase = stime % dp_cycle();
	if (phase >= dp_pass()) return;              	    // don't latch during settle
	if (phase % dp_dwell() != dp_dwell() - 1) return;   // latch at end of each dwell window
	int dst_id = (phase / dp_dwell()) % dp_no_dst();
	for (int i=0; i<DIRECTIONS; i++)
		routing_directions[dst_id][i] = dp_dir[i];
	
	#ifdef DP_DEBUG
	if (dst_id == DP_WATCH_DST) {
		std::cout << "[LATCH] t=" << stime
		          << " phase=" << phase
		          << " dwstep=" << (phase % dp_dwell())
		          << " dst=" << dst_id << " node=" << local_id
		          << " dirs[";
		for (int i=0;i<DIRECTIONS;i++) std::cout << routing_directions[dst_id][i] << " ";
		std::cout << "]" << std::endl;
	}
	#endif

}

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------
vector<int> TRouter::routingFunction(const TRouteData& route_data) 
{
  TCoord position  = id2Coord(route_data.current_id);
  TCoord src_coord = id2Coord(route_data.src_id);
  TCoord dst_coord = id2Coord(route_data.dst_id);
  int dir_in       = route_data.dir_in;
  int dw_no	   = route_data.dw;

  switch (TGlobalParams::routing_algorithm)
    {
    case ROUTING_XY:
     if (TGlobalParams::mesh_dim_z == 1)
       return routingXY(position, dst_coord);
     else
       return routingXYZ(position, dst_coord);

    case ROUTING_WEST_FIRST:
      return routingWestFirst(position, dst_coord);

    case ROUTING_NORTH_LAST:
      return routingNorthLast(position, dst_coord);

    case ROUTING_NEGATIVE_FIRST:
     if (TGlobalParams::mesh_dim_z == 1)
      return routingNegativeFirst(position, dst_coord);
     else 
      return routingNegativeFirst3D(position, dst_coord);

    case ROUTING_ODD_EVEN:
     if (TGlobalParams::mesh_dim_z == 1)
     	 return routingOddEven(position, src_coord, dst_coord);
     else
     	return routingOddEven3D(route_data);    
	
	case ROUTING_ODD_EVEN_BALANCED:
     if (TGlobalParams::mesh_dim_z == 1)
     	return routingOddEven(position, src_coord, dst_coord);
     else
     	return routingOddEvenBalanced(route_data);
	
    case ROUTING_DYAD:
      return routingDyAD(position, src_coord, dst_coord);

    case ROUTING_FULLY_ADAPTIVE:
      return routingFullyAdaptive(position, dst_coord);
   
    case ROUTING_TABLE_BASED:
      return routingTableBased(dir_in, position, dst_coord);
    
   case ROUTING_DW_XYZ:
       return routingDW_XYZ(position, dst_coord, dw_no);
     
   case ROUTING_DW_ODD_EVEN:
       return routingDwOddEven(route_data);

  case ROUTING_ODD_EVEN_3DNM:
       return routingOddEven3DNM(route_data);

    default:
      assert(false);
    }

  // something weird happened, you shouldn't be here
  return (vector<int>)(0);
}

//---------------------------------------------------------------------------

int TRouter::route(const TRouteData& route_data)
{

  if (route_data.dst_id == local_id)
    return DIRECTION_LOCAL;

  vector<int> candidate_channels = routingFunction(route_data);

  return selectionFunction(candidate_channels,route_data);
}

//---------------------------------------------------------------------------

void TRouter::NoP_report() const
{
    TNoP_data NoP_tmp;
      cout << sc_time_stamp().to_double()/1000 << ": Router[" << local_id << "] NoP report: " << endl;

      for (int i=0;i<DIRECTIONS; i++) 
      {
	  NoP_tmp = NoP_data_in[i].read();
	  if (NoP_tmp.sender_id!=NOT_VALID)
	    cout << NoP_tmp;
      }
}
//---------------------------------------------------------------------------

int TRouter::NoPScore(const TNoP_data& nop_data, const vector<int>& nop_channels) const
{
    int score = 0;

    for (unsigned int i=0;i<nop_channels.size();i++)
    {
	int available;

	if (nop_data.channel_status_neighbor[nop_channels[i]].available)
	    available = 1; 
	else available = 0;

	int free_slots = nop_data.channel_status_neighbor[nop_channels[i]].free_slots;

	score += available*free_slots;
    }

    return score;
}
//---------------------------------------------------------------------------

int TRouter::selectionNoP(const vector<int>& directions, const TRouteData& route_data)
{
  vector<int> neighbors_on_path;
  vector<int> score;
  int direction_selected = NOT_VALID;

  int current_id = route_data.current_id;

  for (uint i=0; i<directions.size(); i++)
  {
    // get id of adjacent candidate
    int candidate_id = getNeighborId(current_id,directions[i]);

  // apply routing function to the adjacent candidate node
    TRouteData tmp_route_data;
    tmp_route_data.current_id = candidate_id;
    tmp_route_data.src_id = route_data.src_id;
    tmp_route_data.dst_id = route_data.dst_id;
    tmp_route_data.dir_in = reflexDirection(directions[i]);


    vector<int> next_candidate_channels = routingFunction(tmp_route_data);

    // select useful data from Neighbor-on-Path input 
    TNoP_data nop_tmp = NoP_data_in[directions[i]].read();

    // store the score of node in the direction[i]
    score.push_back(NoPScore(nop_tmp,next_candidate_channels));
  }

  // check for direction with higher score
  int max_direction = directions[0];
  int max = score[0];
  for (unsigned int i = 0;i<directions.size();i++)
  {
      if (score[i]>max)
      {
	  max_direction = directions[i];
	  max = score[i];
      }
  }

  // if multiple direction have the same score = max, choose randomly.
  
  vector<int> equivalent_directions;

  for (unsigned int i = 0;i<directions.size();i++)
      if (score[i]==max)
	  equivalent_directions.push_back(directions[i]);

  direction_selected =  equivalent_directions[rand() % equivalent_directions.size()]; 

  return direction_selected; 
}

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

int TRouter::selectionDP(const vector<int>& directions, const TRouteData& route_data)
{
  int dst = route_data.dst_id;
  int best_available = NOT_VALID;

  // walk DP rank order (j=0 is best); pick the best-ranked candidate that is free,
  // else remember the best-ranked candidate regardless of availability
  for (int j = 0; j < DIRECTIONS; j++)
    for ( int i = 0; i < directions.size(); i++)
      if (directions[i] == routing_directions[dst][j]) {
        if (reservation_table.isAvailable(directions[i]))
          return directions[i];                 // exit with best free DP direction first
        if (best_available == NOT_VALID)		// 
          best_available = directions[i];        // best DP direction (may be busy)
      }

  if (best_available != NOT_VALID) return best_available;
  return directions[0];                          // no DP match at all: fall back
}
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------


int TRouter::selectionBufferLevel(const vector<int>& directions)
{
  vector<int>  best_dirs;
  int          max_free_slots = 0;
  for (unsigned int i=0; i<directions.size(); i++)
    {
      int free_slots = free_slots_neighbor[directions[i]].read();
      bool available = reservation_table.isAvailable(directions[i]);
      if (available)
	{
	  if (free_slots > max_free_slots) 
	    {
	      max_free_slots = free_slots;
	      best_dirs.clear();
	      best_dirs.push_back(directions[i]);
	    }
	  else if (free_slots == max_free_slots)
	    best_dirs.push_back(directions[i]);
	}
    }

  if (best_dirs.size())
    return(best_dirs[rand() % best_dirs.size()]);
  else
    return(directions[rand() % directions.size()]);

}


//---------------------------------------------------------------------------

int TRouter::selectionRandom(const vector<int>& directions)
{
  return directions[rand() % directions.size()];  
}

//---------------------------------------------------------------------------

int TRouter::selectionFunction(const vector<int>& directions, const TRouteData& route_data)
{
  // not so elegant but fast escape ;)
  if (directions.size()==1) return directions[0];
  
  stats.power.Selection();
  switch (TGlobalParams::selection_strategy)
    {
    case SEL_RANDOM:
      return selectionRandom(directions);
    case SEL_BUFFER_LEVEL:
      return selectionBufferLevel(directions);
    case SEL_NOP:
      return selectionNoP(directions,route_data);
    case SEL_DP:
      return selectionDP(directions,route_data);
    default:
      assert(false);
    }
  
  return 0;	    
}

//---------------------------------------------------------------------------

vector<int> TRouter::routingXY(const TCoord& current, const TCoord& destination)
{
  vector<int> directions;
  
  if (destination.x > current.x)
    directions.push_back(DIRECTION_EAST);
  else if (destination.x < current.x)
    directions.push_back(DIRECTION_WEST);
  else if (destination.y > current.y)
    directions.push_back(DIRECTION_SOUTH);
  else
    directions.push_back(DIRECTION_NORTH);

  return directions;
}

//---------------------------------------------------------------------------

vector<int> TRouter::routingWestFirst(const TCoord& current, const TCoord& destination)
{
  vector<int> directions;

  if (destination.x <= current.x ||
      destination.y == current.y)
    return routingXY(current, destination);

  if (destination.y < current.y)
    {
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_EAST);
    }
  else
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_EAST);
    }

  return directions;
}

//---------------------------------------------------------------------------

vector<int> TRouter::routingNorthLast(const TCoord& current, const TCoord& destination)
{
  vector<int> directions;

  if (destination.x == current.x ||
      destination.y <= current.y)
    return routingXY(current, destination);

  if (destination.x < current.x)
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_WEST);
    }
  else
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_EAST);
    }

  return directions;
}

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

vector<int> TRouter::routingNegativeFirst(const TCoord& current, const TCoord& destination)
{
  vector<int> directions;

  if (destination.x < current.x && destination.y < current.y)
    {
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_WEST);
    }
   else if (destination.x < current.x && destination.y >= current.y)
    {
      directions.push_back(DIRECTION_WEST);
    }
   else if (destination.x >= current.x && destination.y < current.y)
    {
      directions.push_back(DIRECTION_NORTH);
    }
  else if (destination.x > current.x && destination.y == current.y)
    {
      directions.push_back(DIRECTION_EAST);
    }
  else if (destination.x == current.x && destination.y  > current.y)
    {
      directions.push_back(DIRECTION_SOUTH);
    }
  else
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_EAST);
    }

  return directions;
}
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

vector<int> TRouter::routingNegativeFirst3D(const TCoord& current, const TCoord& destination)
{
vector<int> directions;

if (destination.x < current.x && destination.y < current.y && destination.z > current.z )
    {
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_WEST);
      directions.push_back(DIRECTION_DOWN);
    }
  else if (destination.x < current.x && destination.y < current.y && destination.z <= current.z )
    {
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_WEST);
    }
   else if (destination.x < current.x && destination.y >= current.y && destination.z > current.z )
    {
      directions.push_back(DIRECTION_DOWN);
      directions.push_back(DIRECTION_WEST);
    }
   else if (destination.x >= current.x && destination.y < current.y && destination.z > current.z )
    {
      directions.push_back(DIRECTION_DOWN);
      directions.push_back(DIRECTION_NORTH);
    }
   else if (destination.x < current.x && destination.y >= current.y && destination.z <= current.z )
    {
      directions.push_back(DIRECTION_WEST);
    }
   else if (destination.x >= current.x && destination.y < current.y && destination.z <= current.z )
    {
      directions.push_back(DIRECTION_NORTH);
    }
   else if (destination.x >= current.x && destination.y >= current.y && destination.z > current.z )
    {
      directions.push_back(DIRECTION_DOWN);
    }
   else if (destination.x > current.x && destination.y > current.y && destination.z < current.z )
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_UP);
    }
   else if (destination.x > current.x && destination.y > current.y && destination.z == current.z )
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_EAST);
    }
   else if (destination.x > current.x && destination.y == current.y && destination.z < current.z )
    {
      directions.push_back(DIRECTION_UP);
      directions.push_back(DIRECTION_EAST);
    }
   else if (destination.x == current.x && destination.y > current.y && destination.z < current.z )
    {
      directions.push_back(DIRECTION_UP);
      directions.push_back(DIRECTION_SOUTH);
    }
  else
    return routingXYZ(current, destination);


  return directions;
}

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------

vector<int> TRouter::routingOddEven(const TCoord& current, 
				    const TCoord& source, const TCoord& destination)
{
  vector<int> directions;

  int c0 = current.x;
  int c1 = current.y;
  int s0 = source.x;
  //  int s1 = source.y;
  int d0 = destination.x;
  int d1 = destination.y;
  int e0, e1;

  e0 = d0 - c0;
  e1 = -(d1 - c1);

  if (e0 == 0)
    {
      if (e1 > 0)
	directions.push_back(DIRECTION_NORTH);
      else
	directions.push_back(DIRECTION_SOUTH);
    }
  else
    {
      if (e0 > 0)
	{
	  if (e1 == 0)
	    directions.push_back(DIRECTION_EAST);
	  else
	    {
	      if ( (c0 % 2 == 1) || (c0 == s0) )
		{
		  if (e1 > 0)
		    directions.push_back(DIRECTION_NORTH);
		  else
		    directions.push_back(DIRECTION_SOUTH);
		}
	      if ( (d0 % 2 == 1) || (e0 != 1) )
		directions.push_back(DIRECTION_EAST);
	    }
	}
      else
	{
	  directions.push_back(DIRECTION_WEST);
	  if (c0 % 2 == 0)
	    {
	      if (e1 > 0)
		directions.push_back(DIRECTION_NORTH);
	      if (e1 < 0) 
		directions.push_back(DIRECTION_SOUTH);
	    }
	}
    }
  
  if (!(directions.size() > 0 && directions.size() <= 2))
  {
      cout << "\n STAMPACCHIO :";
      cout << source << endl;
      cout << destination << endl;
      cout << current << endl;

  }
  assert(directions.size() > 0 && directions.size() <= 2);
  
  return directions;
}





//---------------------------------------------------------------------------
vector<int> TRouter::routingDyAD(const TCoord& current, 
				 const TCoord& source, const TCoord& destination)
{
  vector<int> directions;

  directions = routingOddEven(current, source, destination);

  if (!inCongestion())
    directions.resize(1);
  
  return directions;
}

//---------------------------------------------------------------------------

vector<int> TRouter::routingFullyAdaptive(const TCoord& current, const TCoord& destination)
{
  vector<int> directions;

  if (destination.x == current.x && destination.y == current.y || 
      destination.x == current.x && destination.z == current.z ||
      destination.z == current.z && destination.y == current.y )
    return routingXYZ(current, destination);


  if  (destination.x > current.x && destination.y > current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_DOWN);
    }
  else if (destination.x > current.x && destination.y > current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_UP);
    }
  else if (destination.x > current.x && destination.y < current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_DOWN);
    }
  else if (destination.x > current.x && destination.y < current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_UP);
    }

  else if (destination.x < current.x && destination.y > current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_WEST);
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_DOWN);
    }
  else if (destination.x < current.x && destination.y > current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_WEST);
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_UP);
    }
  else if (destination.x < current.x && destination.y < current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_WEST);
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_DOWN);
    }
  else if (destination.x < current.x && destination.y < current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_WEST);
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_UP);
    }


  else if (destination.x == current.x && destination.y < current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_UP);
    }
  else if (destination.x == current.x && destination.y < current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_DOWN);
    }
  else if (destination.x == current.x && destination.y > current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_UP);
    }
  else if (destination.x == current.x && destination.y > current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_DOWN);
    }


  else if (destination.x > current.x && destination.y == current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_UP);
    }
  else if (destination.x > current.x && destination.y == current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_DOWN);
    }
  else if (destination.x < current.x && destination.y == current.y && destination.z < current.z)
    {
      directions.push_back(DIRECTION_WEST);
      directions.push_back(DIRECTION_UP);
    }
  else if (destination.x < current.x && destination.y == current.y && destination.z > current.z)
    {
      directions.push_back(DIRECTION_WEST);
      directions.push_back(DIRECTION_DOWN);
    }



  else if (destination.x > current.x && destination.y < current.y && destination.z == current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_NORTH);
    }
  else if (destination.x > current.x && destination.y > current.y && destination.z == current.z)
    {
      directions.push_back(DIRECTION_EAST);
      directions.push_back(DIRECTION_SOUTH);

    }
  else if (destination.x < current.x && destination.y < current.y && destination.z == current.z)
    {
      directions.push_back(DIRECTION_NORTH);
      directions.push_back(DIRECTION_WEST);
    }
  else //(destination.x < current.x && destination.y > current.y && destination.z == current.z)
    {
      directions.push_back(DIRECTION_SOUTH);
      directions.push_back(DIRECTION_WEST);
    }

  
  return directions;
}

//---------------------------------------------------------------------------

vector<int> TRouter::routingTableBased(const int dir_in, const TCoord& current, const TCoord& destination)
{
  TAdmissibleOutputs ao = routing_table.getAdmissibleOutputs(dir_in, coord2Id(destination));
  
  if (ao.size() == 0)
    {
      cout << "dir: " << dir_in << ", (" << current.x << "," << current.y << ") --> "
	   << "(" << destination.x << "," << destination.y << ")" << endl
	   << coord2Id(current) << "->" << coord2Id(destination) << endl;
    }

  assert(ao.size() > 0);

  //-----
  /*
  vector<int> aov = admissibleOutputsSet2Vector(ao);
  cout << "dir: " << dir_in << ", (" << current.x << "," << current.y << ") --> "
       << "(" << destination.x << "," << destination.y << "), outputs: ";
  for (int i=0; i<aov.size(); i++)
    cout << aov[i] << ", ";
  cout << endl;
  */
  //-----

  return admissibleOutputsSet2Vector(ao);
}

//----------------------------------------------------- Added by Ra'ed

vector<int> TRouter::routingXYZ(const TCoord& current, const TCoord& destination)
{
  vector<int> directions;
  
  if (destination.x > current.x)
    directions.push_back(DIRECTION_EAST);
  else if (destination.x < current.x)
    directions.push_back(DIRECTION_WEST);
  else if (destination.y > current.y)
    directions.push_back(DIRECTION_SOUTH);
  else if (destination.y < current.y)
    directions.push_back(DIRECTION_NORTH);
  else if (destination.z < current.z)
    directions.push_back(DIRECTION_UP);
  else 
    directions.push_back(DIRECTION_DOWN);

  return directions;
}
//---------------------------------------------------------------------------
//----------------------------------------------------- Added by Ra'ed

vector<int> TRouter::routingDW_XYZ(const TCoord& current, const TCoord& destination, const int dw_times)
{
  vector<int> directions;
  bool same_column = destination.x == current.x && destination.y == current.y;
  if (dw_level == 0  || dw_level <= dw_times ||  current.z == (TGlobalParams::mesh_dim_z-1) || same_column)
     return routingXYZ(current, destination); // use XYZ routing if 1) no DW level is defined or 2) flit DW routing times exceeded the DW level or 
     					      // 3) the flit at the lowest layer; or 4) the destination in the same column
  else     
    directions.push_back(DIRECTION_DOWN);
    
  return directions;
}
//---------------------------------------------------------------------------

void TRouter::configure(const int _id, 
			const double _warm_up_time,
			const unsigned int _max_buffer_size,
			TGlobalRoutingTable& grt)
{

  clk_multiple =10;  // Nizar (throttling)
  throt_level =1.0; 
  
  local_id = _id;
  stats.configure(_id, _warm_up_time);

  start_from_port = DIRECTION_LOCAL;

  if (grt.isValid())
    routing_table.configure(grt, _id);

  for (int i=0; i<DIRECTIONS+1; i++)
    buffer[i].SetMaxBufferSize(_max_buffer_size);
}

//---------------------------------------------------------------------------

unsigned long TRouter::getRoutedFlits()
{ 
  return routed_flits; 
}

//---------------------------------------------------------------------------

unsigned int TRouter::getFlitsCount()
{
  unsigned count = 0;

  for (int i=0; i<DIRECTIONS+1; i++)
    count += buffer[i].Size();

  return count;
}

//---------------------------------------------------------------------------

double TRouter::getPower()
{
  return stats.power.getPower();
}


//---------------------------------------------------------------------------

double TRouter::getPower_aborted_flits()
{
  return stats.power.getPower_aborted_flits();
}
//---------------------------------------------------------------------------

int TRouter::reflexDirection(int direction) const
{
    if (direction == DIRECTION_NORTH) return DIRECTION_SOUTH;
    if (direction == DIRECTION_EAST) return DIRECTION_WEST;
    if (direction == DIRECTION_WEST) return DIRECTION_EAST;
    if (direction == DIRECTION_SOUTH) return DIRECTION_NORTH;
    if (direction == DIRECTION_UP) return DIRECTION_UP;
    if (direction == DIRECTION_DOWN) return DIRECTION_DOWN;

    // you shouldn't be here
    assert(false);
    return NOT_VALID;
}

//---------------------------------------------------------------------------

int TRouter::getNeighborId(int _id, int direction) const
{
    TCoord my_coord = id2Coord(_id);

    switch (direction)
    {
	case DIRECTION_NORTH:
	    if (my_coord.y==0) return NOT_VALID;
	    my_coord.y--;
	    break;
	case DIRECTION_SOUTH:
	    if (my_coord.y==TGlobalParams::mesh_dim_y-1) return NOT_VALID;
	    my_coord.y++;
	    break;
	case DIRECTION_EAST:
	    if (my_coord.x==TGlobalParams::mesh_dim_x-1) return NOT_VALID;
	    my_coord.x++;
	    break;
	case DIRECTION_WEST:
	    if (my_coord.x==0) return NOT_VALID;
	    my_coord.x--;
	    break;
	case DIRECTION_UP:
	    if (my_coord.z==1) return NOT_VALID;
	    //my_coord.x++;
	    break;
	case DIRECTION_DOWN:
	    if (my_coord.z==TGlobalParams::mesh_dim_z-1) return NOT_VALID;
	    my_coord.z--;
	    break;
	default:
	    cout << "direction not valid : " << direction;
	    assert(false);
    }

    int neighbor_id = coord2Id(my_coord);

  return neighbor_id;
}

//---------------------------------------------------------------------------

bool TRouter::inCongestion()
{
  for (int i=0; i<DIRECTIONS; i++)
    {
      int flits = TGlobalParams::buffer_depth - free_slots_neighbor[i];
      if (flits > (int)(TGlobalParams::buffer_depth * TGlobalParams::dyad_threshold))
	return true;
    }

  return false;
}

// ---------------------------------------------------------------------------
// Update the cost function on the DP-unit -- added by Ra'ed, Modified by <Nizar>
// Three-phase control: measure ONLY during SETTLE (new tables fully in effect),
// publish the cost at SETTLE end so dpProcess snapshots it at the next CONVERGE
// start (phase==0). CONVERGE-phase traffic is discarded (routes still changing).
// void TRouter::cost_to_go()
// {
	// if (TGlobalParams::selection_strategy != SEL_DP)
		// return;

	// int stime = (int)(sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);
	// int phase = stime % dp_cycle();

	// if (phase == dp_pass())                 // SETTLE begins: reset, measure new-policy traffic cleanly
	// {
		// traffic_counter = 0;
	// }
	// else if (phase == dp_cycle() - 1)       // SETTLE ends: publish cost for the next CONVERGE snapshot
	// {
		// int dp_cost = (100 * traffic_counter) / (dp_settle() * 4);
		// local_dp_cost.write(dp_cost);
	// }
// }

//cost to go buffer level based per channel <Nizar> 
// void TRouter::cost_to_go()
// {
	// if (TGlobalParams::selection_strategy != SEL_DP)
		// return;

	// int stime = (int)(sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);
	// int phase = stime % dp_cycle();
	
	// if (stime%TGlobalParams::tcu_interval == 0) {
	//	cost_to_go, at cinterval boundary:
		// for (int d = 0; d < DIRECTIONS; d++) {
			// int maxb = TGlobalParams::buffer_depth;
			// int avg = channel_samples ? channel_load[d] / channel_samples : 0;
			// dp_channel_cost[d] = min(100, (100 * avg) / maxb);   // normalize 0..100
			// local_dp_cost[d].write(dp_channel_cost[d]);
			// channel_load[d] = 0;
		// }
		// channel_samples = 0;
	// }

	// if (phase == dp_pass())                 // SETTLE begins: reset, measure new-policy traffic cleanly
	// {
		// traffic_counter = 0;
	// }
	// else if (phase == dp_cycle() - 1)       // SETTLE ends: publish cost for the next CONVERGE snapshot
	// {
		// int dp_cost = (100 * traffic_counter) / (dp_settle() * 4);
		// local_dp_cost.write(dp_cost);
	// }
// }


// cost to go: buffer-level based, per channel <Nizar>
void TRouter::cost_to_go()
{
	if (TGlobalParams::selection_strategy != SEL_DP)
		return;

	int stime = (int)(sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);

		if (stime % TGlobalParams::tcu_interval == 0) {
			#ifdef DP_DEBUG
				if (local_id == 4 && stime % TGlobalParams::tcu_interval == 0)
				std::cerr << "load[0]=" << channel_load[0] << " samples=" << channel_samples 
				<< " avg0=" << (channel_samples?channel_load[0]/channel_samples:0) << "\n";

			#endif
    
		int maxb = TGlobalParams::buffer_depth;
		for (int d = 0; d < DIRECTIONS; d++) {
			// avg occupancy as a percentage of buffer, computed without losing the fraction
			int avg_pct = channel_samples ? (100 * channel_load[d]) / (channel_samples) : 0;
			dp_channel_cost[d] = avg_pct;   // 0..100, keeps sub-integer averages
			local_dp_cost[d].write(dp_channel_cost[d]);
						channel_load[d] = 0;
		}
		channel_samples = 0;
	}
}
//---------------------------------------------------------------------------
// 3D Odd Even <Nizar>
vector<int> TRouter::routingOddEven3D(const TRouteData& route_data)
{
  TCoord current  	= id2Coord(route_data.current_id);
  TCoord source 	= id2Coord(route_data.src_id);
  TCoord destination 	= id2Coord(route_data.dst_id);
  int dir_in = route_data.dir_in;

   vector<int> directions;
   int sz=source.z;
   int cz=current.z;
   int dz=destination.z;
   
   //int sx=source.x;
   int cx=current.x;
   int dx=destination.x;
   
   //int sy=source.y;
   int cy=current.y;
   int dy=destination.y;

   int ex = dx-cx;
   int ey = dy-cy;
   int ez = dz-cz;

   //bool better_diversity =(((cz % 2==0)  && ex>ey) || ((cz%2==1) && ex<ey));
   
// for flits moving in the z direction source xy is the xy of the xy plane enetry point 
    if ((dir_in ==DIRECTION_UP) || (dir_in ==DIRECTION_DOWN))
	{
	source.x=current.x;
	source.y=current.y;
	}  // */

  if (ez == 0)
		directions=routingOddEven(current, source, destination);

  else
    {
	  if (ez > 0)   // z direction is +ve (going down)
	    {
		if ((ex==0) && (ey == 0))  // at the xy of destination 
			directions.push_back(DIRECTION_DOWN);
	    else
	    	{
	      	 if ((cz % 2 == 1) || (cz==sz))   //
	 		directions=routingOddEven(current, source, destination);
				
  		 if ((dz % 2 == 1) || (ez != 1))
		  	directions.push_back(DIRECTION_DOWN);
		}
		
	    } // z direction is +ve
	  
	  else   // z direction is -ve ( going up)
		{
		  // need xy-plane routing and the z plane is even	
		directions.push_back(DIRECTION_UP);

	        if ((ex!=0 || ey!=0) &&  (cz % 2 == 0) )  
			directions=routingOddEven(current, source, destination);
		

	        } // z direction is -ve
    } //ez==0

assert (directions.size()>0);
return directions;  
}



//minimum odd-even row-wise <Nizar> 
vector<int> TRouter::routingOddEven0(const TCoord& current, 
				    const TCoord& source, const TCoord& destination)
{
  vector<int> directions;

  int c0 = current.x;
  int c1 = current.y;
  int s0 = source.x;
  int s1 = source.y;
  int d0 = destination.x;
  int d1 = destination.y;
  int e0, e1;

  e0 = -(d0 - c0);
  e1 = d1 - c1;

  if (e1 == 0)
    {
       if (e0 > 0)
		directions.push_back(DIRECTION_WEST);
       if (e0 < 0)
		directions.push_back(DIRECTION_EAST);
    }
  else
     {
      if (e1 > 0)
	{
	  if (e0 == 0)
	    directions.push_back(DIRECTION_SOUTH);
	  else
	    {
	      if ( (c1 % 2 == 1) || (c1 == s1) )
		{
		if (e0 > 0)
			directions.push_back(DIRECTION_WEST);
	        if (e0 < 0)
			directions.push_back(DIRECTION_EAST);
		}
	      if ( (d1 % 2 == 1) || (e1 != 1) )
		directions.push_back(DIRECTION_SOUTH);
	    }
	}
      else
	{
	  directions.push_back(DIRECTION_NORTH);
	  if (c1 % 2 == 0)
	    {
	       if (e0 > 0)
			directions.push_back(DIRECTION_WEST);
	       if (e0 < 0)
			directions.push_back(DIRECTION_EAST);
	    }
	}
    }
  
  if (!(directions.size() > 0 && directions.size() <= 2))
  {
      cout << "\n STAMPACCHIO :";
      cout << source << endl;
      cout << destination << endl;
      cout << current << endl;

  }
  assert(directions.size() > 0 && directions.size() <= 2);
  
  return directions;
}

// minimum odd-even column-wise <Nizar)
vector<int> TRouter::routingOddEven1(const TCoord& current, 
				    const TCoord& source, const TCoord& destination)
{
  vector<int> directions;
  int c0 = current.x;
  int c1 = current.y;
  int s0 = source.x;
  //  int s1 = source.y;
  int d0 = destination.x;
  int d1 = destination.y;
  int e0, e1;

  e0 = d0 - c0;
  e1 = -(d1 - c1);

  if (e0 == 0)
    {
      if (e1 > 0)
	directions.push_back(DIRECTION_NORTH);
      else
	directions.push_back(DIRECTION_SOUTH);
    }
  else
   {
      if (e0 > 0)  // Eastwards
	  {
	    if (e1 == 0)
		    directions.push_back(DIRECTION_EAST);
	    
	    else
		{
		if ( (c0 % 2 == 0) || (c0 == s0) )
				{
				if (e1 > 0)
					directions.push_back(DIRECTION_NORTH);
				else
					directions.push_back(DIRECTION_SOUTH);
				}
	    if ( (d0 % 2 == 0) || (e0 != 1) )
		  		 directions.push_back(DIRECTION_EAST);
		
		
	    }
      }	// e0 >0
      else // e0<0 (// Weststwards)
	  {
		directions.push_back(DIRECTION_WEST);
		if (c0 % 2 == 1)
		{
				if (e1 > 0)
					directions.push_back(DIRECTION_NORTH);
				else
					directions.push_back(DIRECTION_SOUTH);
			
		}
	  } // e0<0
  }// e0!= 0
  
  return directions;
} 





//Non-minimum Odd Even <Nizar>
vector<int> TRouter::routingOddEvenNM(const TCoord& current, 
				    const TCoord& source, const TCoord& destination, const int dir_in)
{
  vector<int> directions;
  int c0 = current.x;
  int c1 = current.y;
  int s0 = source.x;
  //  int s1 = source.y;
  int d0 = destination.x;
  int d1 = destination.y;
  int e0, e1;

  e0 = d0 - c0;
  e1 = -(d1 - c1);

  if (e0 == 0)
    {
      if (e1 > 0)
	directions.push_back(DIRECTION_NORTH);
      else
	directions.push_back(DIRECTION_SOUTH);
    }
  else
   {
      if (e0 > 0)
	  {
	    if (e1 == 0)
		  {
		    directions.push_back(DIRECTION_EAST);
			if ((c0 % 2 == 1 || c0 == s0) && e0 != 1)			 // for NM routing  
			     {
				if(c1 > 0 && dir_in != DIRECTION_NORTH ) 	
			              directions.push_back(DIRECTION_NORTH);
                   		if (c1 < TGlobalParams::mesh_dim_y-1 && dir_in != DIRECTION_SOUTH) 
				       directions.push_back(DIRECTION_SOUTH);	
			     }
		  }
	    
	    else
		{
			if ( (d0 % 2 == 0) && (e0 == 1) )
				{
				if (e1 > 0)
					directions.push_back(DIRECTION_NORTH);
				else
					directions.push_back(DIRECTION_SOUTH);
				}
			else
			{
				if ( (c0 % 2 == 1) || (c0 == s0) )
				{
					if(c1 > 0 && dir_in != DIRECTION_NORTH ) 	
						directions.push_back(DIRECTION_NORTH);
					if (c1 < TGlobalParams::mesh_dim_y-1 && dir_in != DIRECTION_SOUTH) 
						directions.push_back(DIRECTION_SOUTH);	
				}
	          	if ( (d0 % 2 == 1) || (e0 != 1) )
		     		 directions.push_back(DIRECTION_EAST);
			}
	    }
      }	// e0 >0
      else // e0<0
	  {
		directions.push_back(DIRECTION_WEST);
		if (c0 % 2 == 0)
		{
			if(c1 > 0 && dir_in != DIRECTION_NORTH ) 	
			          directions.push_back(DIRECTION_NORTH);
            		if(c1 < TGlobalParams::mesh_dim_y-1 && dir_in != DIRECTION_SOUTH) 
				  directions.push_back(DIRECTION_SOUTH);
		}
	  } // e0<0
  }// e0!= 0
  
  return directions;
} 



vector<int> TRouter::routingOddEvenNM0(const TCoord& current, 
				    const TCoord& source, const TCoord& destination, const int dir_in)
{
  vector<int> directions;

  int c0 = current.x;
  int c1 = current.y;
  int s0 = source.x;
  int s1 = source.y;
  int d0 = destination.x;
  int d1 = destination.y;
  int e0, e1;

  e0 = -(d0 - c0);
  e1 = d1 - c1;

  if (e1 == 0)
    {
       if (e0 > 0)
		directions.push_back(DIRECTION_WEST);
       if (e0 < 0)
		directions.push_back(DIRECTION_EAST);
    }
  else
     {
      if (e1 > 0)
	{
	  if (e0 == 0)
            {		 
	    directions.push_back(DIRECTION_SOUTH);
	    if ((c1 % 2 == 1 || c1 == s1) && e1 != 1)			 // for NM routing  
		{
			if(c0 > 0 && dir_in != DIRECTION_WEST) 	
			       directions.push_back(DIRECTION_WEST);
                	if (c0 < TGlobalParams::mesh_dim_x-1 && dir_in != DIRECTION_EAST) 
			       directions.push_back(DIRECTION_EAST);	
		}
	    }
	  else
	    {
	    	       if ( (d1 % 2 == 0) && (e1 == 1) )
			{
				if (e0 > 0)
					directions.push_back(DIRECTION_WEST);
	      			if (e0 < 0)
					directions.push_back(DIRECTION_EAST);
			}
			else
			{
				if ((c1 % 2 == 1) || (c1 == s1) )
				{
					if(c0 > 0 && dir_in != DIRECTION_WEST) 	
			       			directions.push_back(DIRECTION_WEST);
		                	if (c0 < TGlobalParams::mesh_dim_x-1 && dir_in != DIRECTION_EAST) 
					       directions.push_back(DIRECTION_EAST);	
				}
			      if ( (d1 % 2 == 1) || (e1 != 1) )
					directions.push_back(DIRECTION_SOUTH);
			}
	    }
	}
      else //e1 <  0
	{
	  directions.push_back(DIRECTION_NORTH);
	  if (c1 % 2 == 0)
	    {
		if(c0 > 0 && dir_in != DIRECTION_WEST) 	
			directions.push_back(DIRECTION_WEST);
	      	if (c0 < TGlobalParams::mesh_dim_x-1 && dir_in != DIRECTION_EAST) 
	 	        directions.push_back(DIRECTION_EAST);	    
	    }
	} 
    }

  return directions;
}

vector<int> TRouter::routingOddEvenNM1(const TCoord& current, 
				    const TCoord& source, const TCoord& destination, const int dir_in)
{
  vector<int> directions;
  int c0 = current.x;
  int c1 = current.y;
  int s0 = source.x;
  //  int s1 = source.y;
  int d0 = destination.x;
  int d1 = destination.y;
  int e0, e1;

  e0 = d0 - c0;
  e1 = -(d1 - c1);

  if (e0 == 0)
    {
      if (e1 > 0)
	directions.push_back(DIRECTION_NORTH);
      else
	directions.push_back(DIRECTION_SOUTH);
    }
  else
   {
      if (e0 > 0)
	  {
	    if (e1 == 0)
		  {
		    directions.push_back(DIRECTION_EAST);
			if ((c0 % 2 == 0 || c0 == s0) && e0 != 1)			 // for NM routing  
			     {
				if(c1 > 0 && dir_in != DIRECTION_NORTH ) 	
			              directions.push_back(DIRECTION_NORTH);
                   		if (c1 < TGlobalParams::mesh_dim_y-1 && dir_in != DIRECTION_SOUTH) 
				       directions.push_back(DIRECTION_SOUTH);	
			     }
		  }
	    
	    else  //(e1 !=0)
		{
			if ( (d0 % 2 == 1) && (e0 == 1) )
				{
				if (e1 > 0)
					directions.push_back(DIRECTION_NORTH);
				else
					directions.push_back(DIRECTION_SOUTH);
				}
			else
			{
				if ( (c0 % 2 == 0) || (c0 == s0) )
				{
					if(c1 > 0 && dir_in != DIRECTION_NORTH ) 	
						directions.push_back(DIRECTION_NORTH);
					if (c1 < TGlobalParams::mesh_dim_y-1 && dir_in != DIRECTION_SOUTH) 
						directions.push_back(DIRECTION_SOUTH);	
				}
	          	if ( (d0 % 2 == 0) || (e0 != 1) )
		     		 directions.push_back(DIRECTION_EAST);
			}
	    }
      }	// e0 >0
      else // e0<0
	  {
		directions.push_back(DIRECTION_WEST);
		if (c0 % 2 == 1)
		{
			if(c1 > 0 && dir_in != DIRECTION_NORTH ) 	
			          directions.push_back(DIRECTION_NORTH);
            		if(c1 < TGlobalParams::mesh_dim_y-1 && dir_in != DIRECTION_SOUTH) 
				  directions.push_back(DIRECTION_SOUTH);
		}
	  } // e0<0
  }// e0!= 0
  
  return directions;
} 

//Vertically & Horizontally Non minumum Odd Even <Nizar>
vector<int> TRouter::routingDwOddEven(const TRouteData& route_data)
{
  TCoord current  	= id2Coord(route_data.current_id);
  TCoord source 	= id2Coord(route_data.src_id);
  TCoord destination 	= id2Coord(route_data.dst_id);
  int dir_in = route_data.dir_in;

  vector<int> directions;
  
  int cx = current.x;
  int cy = current.y;
  int cz = current.z;
  
  int sx = source.x;
  int sy = source.y;
  int sz = source.z;
  
  int dx = destination.x;
  int dy = destination.y;
  int dz = destination.z;

  //int dirz=cz-sz;   // to check if a packet is in a nonminimum z route
  //bool dwrange= true; //(dirz >=0 && dirz < 1);

  //int e0, e1, e2;
   
// for flits moving in the z direction source xy is the xy of the xy-plane enetry point 
    if ((dir_in ==DIRECTION_UP) || (dir_in ==DIRECTION_DOWN))
	{
	source.x=current.x;
	source.y=current.y;
	}  //  *

if (dz > cz )   // packet is moving DOWN
	directions.push_back(DIRECTION_DOWN);

if (dz < cz)  // UP
	{
	if ((dx==cx) & (dy==cy))
		directions.push_back(DIRECTION_UP);
		else 
		{
 		directions=routingOddEvenNM(current, source, destination, dir_in);

      		if (cz < TGlobalParams::mesh_dim_z-1 )
	    		 directions.push_back(DIRECTION_DOWN); 	
		}

	}  // end moving UP
  
  if (cz == dz)  // co-palanr
     {
	directions=routingOddEvenNM(current, source, destination, dir_in);

	
     if (cz < TGlobalParams::mesh_dim_z-1 )
     	directions.push_back(DIRECTION_DOWN); 	
     }

/*
if (route_data.current_id==11 && route_data.dst_id == 18)
{
	for (int i=0; i<directions.size(); i++)
		cout<<directions[i]<<" " ;
cout<<endl;
} // */
 return directions;
}

vector<int> TRouter::routingOddEven3DNM(const TRouteData& route_data)
{
  TCoord current  	= id2Coord(route_data.current_id);
  TCoord source 	= id2Coord(route_data.src_id);
  TCoord destination 	= id2Coord(route_data.dst_id);
  int dir_in = route_data.dir_in;

   vector<int> directions;
   int sz=source.z;
   int cz=current.z;
   int dz=destination.z;
   
   //int sx=source.x;
   int cx=current.x;
   int dx=destination.x;
   
   //int sy=source.y;
   int cy=current.y;
   int dy=destination.y;

   int ex = dx-cx;
   int ey = dy-cy;
   int ez = dz-cz;
   int dirz=cz-sz;   // to check if a packet is in a nonminimum z route
   bool dwrange= true; // (dirz >=0 && dirz <1);

/*// for flits moving in the z direction source xy is the xy of the xy plane enetry point 
    if ((dir_in ==DIRECTION_UP) || (dir_in ==DIRECTION_DOWN))
	{
	source.x=current.x;
	source.y=current.y;
	}  // */

  if (ez == 0)
	{
	if (cz%2==0) // for even z use the modified OE routing
		directions=routingOddEvenNM(current, source, destination, dir_in);
	else // for odd use convensional OE routing
		directions=routingOddEvenNM0(current, source, destination, dir_in);
	// to move down: cz<dimz AND no reflection AND [either continuing to down OR this is even Z]	
	if (cz < TGlobalParams::mesh_dim_z-1 && dir_in !=DIRECTION_DOWN)// && cz % 2 == 0 && dwrange )
    		directions.push_back(DIRECTION_DOWN); 
	}
  else
    {
	if (ez < 0)   // z direction is -ve
	{
	    if ((ex==0) && (ey == 0))  // on the xy position 
			directions.push_back(DIRECTION_UP);
	    else
	    {
	      //if ( cz % 2 == 1 || cz == sz || dirz > 0)
			if (cz%2==0) 
				directions=routingOddEvenNM(current, source, destination, dir_in);
			else 
				directions=routingOddEvenNM0(current, source, destination, dir_in);

	      //if ( (dz % 2 == 1 || ez != -1)  && dir_in !=DIRECTION_UP && dirz < 0)
	      //		directions.push_back(DIRECTION_UP);

   	      if ((cz < TGlobalParams::mesh_dim_z-1) && dir_in !=DIRECTION_DOWN) //&&  cz % 2 == 0 && dwrange)
    	      		directions.push_back(DIRECTION_DOWN); 

	    }
	}
	  else   // ez > 0		
	  {
	        if ((ex!=0 || ey!=0))//&&  (cz % 2 == 0))  // need xy-plane routing and the z plane is even
		{
			if (cz%2==0) 
				directions=routingOddEvenNM(current, source, destination, dir_in);
			else 
				directions=routingOddEvenNM0(current, source, destination, dir_in);
		}
		
		 directions.push_back(DIRECTION_DOWN);
	  }
    }

return directions;  
}


// Balanced odd-even routing for 3D NoC <Nizar>
// In-plane: plane-parity rule — even plane row-wise (OE0), odd plane column-wise (OE1).
// Vertical: gating identical to the published routingOddEven3D (j2/c2) — these
// conditions are the inter-plane cycle-breaking rules; do not simplify them.
// MUST stay in lockstep with DPNode::can_turnOddEvenBalanced.
vector<int> TRouter::routingOddEvenBalanced(const TRouteData& route_data)
{
  TCoord current     = id2Coord(route_data.current_id);
  TCoord source      = id2Coord(route_data.src_id);
  TCoord destination = id2Coord(route_data.dst_id);
  int dir_in = route_data.dir_in;

  vector<int> directions;

  // flits arriving vertically: source xy becomes the plane entry point
  if ((dir_in == DIRECTION_UP) || (dir_in == DIRECTION_DOWN))
  {
    source.x = current.x;
    source.y = current.y;
  }

  int sz = source.z,      cz = current.z,  dz = destination.z;
  int ex = destination.x - current.x;
  int ey = destination.y - current.y;
  int ez = dz - cz;

  if (ez == 0)
  {
    // on destination plane: parity-split in-plane only
    if (cz % 2 == 0)
      directions = routingOddEven0(current, source, destination); // row-wise
    else
      directions = routingOddEven1(current, source, destination); // column-wise
  }
  else if (ez > 0)   // going down
  {
    if ((ex == 0) && (ey == 0))
      directions.push_back(DIRECTION_DOWN);      // aligned: descend only
    else
    {
      if ((cz % 2 == 1) || (cz == sz))           // in-plane on odd or source plane
      {
        if (cz % 2 == 0)
          directions = routingOddEven0(current, source, destination);
        else
          directions = routingOddEven1(current, source, destination);
      }
      if ((dz % 2 == 1) || (ez != 1))            // descend under published condition
        directions.push_back(DIRECTION_DOWN);
    }
  }
  else               // ez < 0, going up
  {
    // exclusivity preserved from the published algorithm:
    // unaligned + even plane -> in-plane ONLY; otherwise UP only
    if ((ex != 0 || ey != 0) && (cz % 2 == 0))
      directions = routingOddEven0(current, source, destination); // even plane: row-wise
    else
      directions.push_back(DIRECTION_UP);
  }

  assert(directions.size() > 0);
  return directions;
}