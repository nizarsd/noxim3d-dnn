#include "DPNode.h"
#include <algorithm>
#define alpha 1


void DPNode::dpProcess()
{
	// Gating for other selection methods
	if (TGlobalParams::selection_strategy != SEL_DP)  return;
	



	int stime  = (int) (sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);

	
	// One destination held for `dwell` (>= mesh diameter) consecutive cycles so its
	// cost field fully converges in place before advancing to the next destination.
	// measure -> snapshot -> DP converge (config)-> settle for ss measurement 
	int phase = stime % dp_cycle();
	
	if (phase >= dp_pass()) return;              // SETTLE: DP idle
	
		dst_id = (phase / dp_dwell()) % dp_no_dst(); // converge-phase destination
	


	if (reset.read())
	{
		for (int i=0; i<DIRECTIONS; i++)
		{
			dp_tx[i].write  (BIG_VALUE);
			dp_dir[i].write (NOT_VALID);
			frozen_local_cost[i] = 0;
		}
		for (int d=0; d<DPSIZE; d++)
			for (int i=0; i<DIRECTIONS; i++)
				cost_mem[d][i] = BIG_VALUE;
			
		return;
	}

	if (!dp_clock.posedge())  return;
	
	// for single cost metric
	// if (phase == 0) 
		// frozen_local_cost = local_dp_cost.read();
	
	if ((phase % dp_dwell()) == 0) {
		for (int i=0; i<DIRECTIONS; i++)
			frozen_local_cost[i] = local_dp_cost[i].read();
	}

	// Destination node: cost anchor (0 to itself), every cycle of its dwell window.
	if (local_id == dst_id)
	{
		for (int i=0; i<DIRECTIONS; i++)
		{
			dp_tx[i].write (0);
			dp_dir[i].write(NOT_VALID);
			cost_mem[dst_id][i] = 0;
		}
		
		#ifdef DP_DEBUG
		if (dst_id == DP_WATCH_DST)
			std::cout << "[DP] dst=" << dst_id << " step=" << (stime % dp_dwell())
					  << " node=" << local_id << " ANCHOR mincost=0" << std::endl;
		#endif
		
		return;
	}
	// Exchange rate between distance and congestion: one MAXIMALLY congested hop
	// should cost about the same as one extra hop, so this must track the cost
	// metric's range (occupancy 0-100, wait 0-DP_COST_WAIT_MAX).  Inert under
	// minimal routing -- every legal output is one hop closer, so it is added
	// identically to every candidate and cancels -- but load-bearing under
	// oddevennm, where candidates sit at different distances.
	int HOP_COST = (TGlobalParams::dp_cost_metric == DP_COST_WAIT)
	             ? DP_COST_WAIT_MAX : 100;
	// RELAX (every cycle of the dwell): dp_rx holds neighbours' stored costs for
	// this dst_id, coherent because all nodes hold the same dst_id for the window.
	int rx_dp_cost[DIRECTIONS];
	for (int i=0; i<DIRECTIONS; i++)
		rx_dp_cost[i] = (dp_rx[i] >= BIG_VALUE) ? BIG_VALUE
		              : (int)(dp_rx[i]*alpha) + frozen_local_cost[i] + HOP_COST; // HOP_COST may be not needed for min routing 

	int sorted_ports[] = {0,1,2,3,4,5};
	BubbleSort(rx_dp_cost, sorted_ports);       // ports ordered by ascending cost

	int dp_cost[DIRECTIONS];
	for (int i=0; i<DIRECTIONS; i++)
		dp_cost[i] = BIG_VALUE;

// Build this destination's turn-legality table once, then reuse it. can_turn()
// is constant for the whole run, so this moves ~25% of runtime off the hot path.
if (!legal_cached[dst_id]) {
    for (int a = 0; a < DIRECTIONS; a++)
        for (int b = 0; b < DIRECTIONS; b++)
            legal_cache[dst_id][a][b] = can_turn(a, b, dst_id);
    legal_cached[dst_id] = true;
}

// Min cost per input direction j, over legal-turn output ports (i).
for (int i = 0; i < DIRECTIONS; i++)
    for (int j = 0; j < DIRECTIONS; j++)
        if (legal_cache[dst_id][j][sorted_ports[i]] && dp_cost[j] > rx_dp_cost[sorted_ports[i]])
            dp_cost[j] = rx_dp_cost[sorted_ports[i]];

// DP convergence must continue every cycle.
for (int i = 0; i < DIRECTIONS; i++) {
    dp_tx[i].write(dp_cost[i]);
    cost_mem[dst_id][i] = dp_cost[i];
}

// Publish ranking one clock before the router latches it.
if ((phase % dp_dwell()) == dp_dwell() - 2) {
    // DPSYNC=<node> -- verify DPNode and TRouter agree on which dst_id is live.
    static const char* sy = getenv("DPSYNC");
    if (sy && local_id == atoi(sy))
        std::cerr << "PUB," << stime << "," << phase << "," << dst_id << "\n";
    for (int i = 0; i < DIRECTIONS; i++) {
        if (rx_dp_cost[sorted_ports[i]] >= BIG_VALUE)
            dp_dir[i].write(NOT_VALID);
        else
            dp_dir[i].write(sorted_ports[i]);
    }
}
    
// ---- DEBUG: convergence trace for one fixed destination ----------------
// Compile with -DDP_DEBUG. Traces cost to DP_WATCH_DST only.
#ifdef DP_DEBUG
	if (dst_id == DP_WATCH_DST)
	{
		int mincost = BIG_VALUE;
		for (int i=0; i<DIRECTIONS; i++)
			if (dp_cost[i] < mincost) mincost = dp_cost[i];

		int step = stime % dp_dwell();          // hop index within this dst's window
		int nx = local_id % TGlobalParams::mesh_dim_x;
		int ny = (local_id / TGlobalParams::mesh_dim_x) % TGlobalParams::mesh_dim_y;
		int nz = local_id / (TGlobalParams::mesh_dim_x*TGlobalParams::mesh_dim_y);
		std::cout << "[DP] dst=" << dst_id << " step=" << (stime % dp_dwell())
				  << " node=" << local_id << "(" << nx << "," << ny << "," << nz << ")"
				  << " mincost=" << (mincost>=BIG_VALUE ? -1 : mincost)
				  << " frz[";
		for(int i=0;i<DIRECTIONS;i++) std::cout << frozen_local_cost[i] << " ";
		std::cout << "] rx[";
		for(int i=0;i<DIRECTIONS;i++) std::cout << dp_rx[i].read() << " ";
		std::cout << "] perdir[";
		for(int i=0;i<DIRECTIONS;i++) std::cout << (dp_cost[i]>=BIG_VALUE?-1:dp_cost[i]) << " ";
		std::cout << "]" << std::endl;
		
	}
#endif

}



void  DPNode::configure(const int _local_id)
{
  local_id = _local_id;
  for (int d = 0; d < DPSIZE; d++)
      legal_cached[d] = false;
}

// check if the turn is allowed
bool  DPNode::can_turn(int dir_in, int dir_out, int dst_id)
{

 switch (TGlobalParams::routing_algorithm) {

  case ROUTING_NEGATIVE_FIRST: 
	    return   can_turnNegativeFirst(dir_in, dir_out, dst_id);
	    break;
  case ROUTING_ODD_EVEN: 
	    return	can_turnOddEven(dir_in, dir_out, dst_id);
	    break;
  case ROUTING_FULLY_ADAPTIVE:
        return can_turnFullyAdaptive(dir_in, dir_out, dst_id);
        break;
 case ROUTING_DW_ODD_EVEN: 
	    return	can_turnDwOddEven(dir_in, dir_out, dst_id);
	    break;
case ROUTING_ODD_EVEN_3DNM: 
	    return	can_turnOddEvenNM(dir_in, dir_out, dst_id);
	    break;

case ROUTING_ODD_EVEN_BALANCED:
    /*
     * TRouter falls back to plain 2D odd-even when mesh_dim_z == 1.
     * DP legality must follow the same dispatch.
     */
    if (TGlobalParams::mesh_dim_z == 1)
        return can_turnOddEven(dir_in, dir_out, dst_id);

    return can_turnOddEvenBalanced(dir_in, dir_out, dst_id);

	  break;

  default:
	return true;
}



}


bool DPNode::can_turnOddEven(int dir_in, int dir_out, int dst_id)
{
    TCoord current     = id2Coord(local_id);
    TCoord destination = id2Coord(dst_id);

    /*
     * In this direction convention, dir_in == dir_out means the packet
     * would immediately go back to the router it came from.
     */
	//if (local_id != dst_id &&
	//	!isMinimalDirection(dir_in, current, destination, true))
	//	return false;

	if (!isMinimalDirection(dir_out, current, destination, false))
		return false;

	if (dir_in == dir_out)
		return false;
	
    vector<int> directions;

    int cz = current.z;
    int dz = destination.z;

    int ex = destination.x - current.x;
    int ey = destination.y - current.y;
    int ez = dz - cz;

    if (ez == 0) {
        directions = routingOddEvenDPStrict(current, destination);
    }
    else if (ez > 0) { // going DOWN
        if ((ex == 0) && (ey == 0)) {
            directions.push_back(DIRECTION_DOWN);
        }
        else {
            /*
             * Real 3D OE had:
             *     (cz % 2 == 1) || (cz == sz)
             *
             * DP does not know true source plane, so it is inferred from the current plane. This is a conservative approximation.
             */
            if (cz % 2 == 1 || dir_in != DIRECTION_UP)
                directions = routingOddEvenDPStrict(current, destination);
            else if ((dz % 2 == 1) || (ez > 1))
                directions.push_back(DIRECTION_DOWN);
        }
    }
    else { // ez < 0, going UP
        /*
         * Preserve vertical exclusivity:
         * unaligned + even plane => in-plane only;
         * otherwise => UP only.
         */
        if ((ex != 0 || ey != 0) && (cz % 2 == 0))
            directions = routingOddEvenDPStrict(current, destination);
        else
            directions.push_back(DIRECTION_UP);
    }

    for (unsigned int i = 0; i < directions.size(); i++) {
        if (dir_out == directions[i])
            return true;
    }

    return false;
}

vector<int> DPNode::routingOddEven(const TCoord& current, 
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


bool DPNode::can_turnNegativeFirst(int dir_in, int dir_out, int dst_id)
{
 int idfrom=224, idto=25; 
 
 vector<int> directions;
 TCoord current  	= id2Coord(local_id);
 TCoord destination 	= id2Coord(dst_id);



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
     directions=routingXYZ(current, destination);


/* if (local_id == idfrom) //&& dst_id==idto) 
{
	cout<<local_id<<current<<"->"<<dst_id<<destination<<"| ";

	for (int i=0; i<directions.size(); i++)
		cout<< directions[i]<<" ";
} // 

/*if (local_id == idfrom)// && dst_id==idto)
	cout<<" from: "<<dir_in<< " to: "<< dir_out<<" is: "<<in_directions<<endl; // */


bool in_directions=false;

for (int i=0; i<directions.size(); i++)
	if(dir_out==directions[i])
		in_directions=true;

return in_directions;

}



vector<int> DPNode::routingXYZ(const TCoord& current, const TCoord& destination)
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

vector<int> DPNode::routingOddEven1(const TCoord& current, 
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
		  {
		    directions.push_back(DIRECTION_EAST);
			if ((c0 % 2 == 0 || c0 == s0) && e0 != 1)			 // for NM routing  
			    {
					if (e1 > 0)
						directions.push_back(DIRECTION_NORTH);
					else
						directions.push_back(DIRECTION_SOUTH);			     
				}
		  }
	    
	    else
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
				if (e1 > 0)
					directions.push_back(DIRECTION_NORTH);
				else
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
				if (e1 > 0)
					directions.push_back(DIRECTION_NORTH);
				else
					directions.push_back(DIRECTION_SOUTH);
			
		}
	  } // e0<0
  }// e0!= 0
  
  return directions;
} 
vector<int> DPNode::routingOddEven0(const TCoord& current, 
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




vector<int> DPNode::routingOddEvenNM(const TCoord& current, 
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
			if (((c0 % 2 == 1) || (c0 == s0)) && (e0 != 1))			 // for NM routing  
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

// odd even non mimumum the Odd Even rules are applied along the row and not the columns  <Nizar>
vector<int> DPNode::routingOddEvenNM0(const TCoord& current, 
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
      else
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


// odd even non mimumum the Odd Even rules are applied as Even-Odd rules <Nizar>
vector<int> DPNode::routingOddEvenNM1(const TCoord& current, 
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
	    
	    else
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

//Vertically dw- Horizontally Odd Even <Nizar>
bool DPNode::can_turnDwOddEven(int dir_in, int dir_out, int dst_id)
{
  TCoord current  	= id2Coord(local_id);
  TCoord destination 	= id2Coord(dst_id);
  TCoord source 	= current;
  //if (dir_in==dir_out)
  //         return false;

  switch ( dir_in ) {

  case DIRECTION_NORTH : 
	     source.y-=1;
	     break;
  case DIRECTION_EAST : 
	    source.x+=1;
	    break;
  case DIRECTION_SOUTH : 
	    source.y+=1;
	    break;
  case DIRECTION_WEST: 
	    source.x-=1;
	    break;
  case DIRECTION_UP : 
	    source.z+=1;
	    break;
  case DIRECTION_DOWN : 
	    source.z-=1;
	    break;
  default:
	// you must not be here !
	assert (false);
}

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
 

if (dz > cz )   // packet is moving DOWN
	directions.push_back(DIRECTION_DOWN);

if (dz < cz)  // UP
	{
	if ((dx==cx) & (dy==cy))
		directions.push_back(DIRECTION_UP);
		else 
		{
 			directions=routingOddEvenNM(current, source, destination, dir_in);

	
      		if (cz < TGlobalParams::mesh_dim_z-1)
	    		 directions.push_back(DIRECTION_DOWN); 	
		}

	}  // end moving UP
  
  if (cz == dz)  // co-palanr
     {
		directions=routingOddEvenNM(current, source, destination, dir_in);

     if (cz < TGlobalParams::mesh_dim_z-1 )
     		directions.push_back(DIRECTION_DOWN); 	
     }



 bool in_directions=false;

for (int i=0; i<directions.size(); i++)
	if(dir_out==directions[i])
		in_directions=true;

return in_directions;

}


bool DPNode::can_turnOddEvenNM(int dir_in, int dir_out, int dst_id)
{
  TCoord current  	= id2Coord(local_id);
  TCoord destination 	= id2Coord(dst_id);
  TCoord source 	= current;

  switch ( dir_in ) {

  case DIRECTION_NORTH : 
	     source.y-=1;
	     break;
  case DIRECTION_EAST : 
	    source.x+=1;
	    break;
  case DIRECTION_SOUTH : 
	    source.y+=1;
	    break;
  case DIRECTION_WEST: 
	    source.x-=1;
	    break;
  case DIRECTION_UP : 
	    source.z+=1;
	    break;
  case DIRECTION_DOWN : 
	    source.z-=1;
	    break;
  default:
	// you must not be here !
	assert (false);
}
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
   int dirz=cz-sz; 
   bool dwrange= true; //(dirz >=0 && dirz <1);

   if (ez == 0)
	{
	if (cz%2==0) // for even z use the modified OE routing
		directions=routingOddEvenNM(current, source, destination, dir_in);
	else // for odd use convensional OE routing
		directions=routingOddEvenNM(current, source, destination, dir_in);
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
				directions=routingOddEvenNM(current, source, destination, dir_in);

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
				directions=routingOddEvenNM(current, source, destination, dir_in);
		}
		
		 directions.push_back(DIRECTION_DOWN);
	  }
    }


bool in_directions=false;

for (int i=0; i<directions.size(); i++)
	if(dir_out==directions[i])
		in_directions=true;

return in_directions;
}

bool DPNode::can_turnOddEvenBalanced(int dir_in, int dir_out, int dst_id)
{
    TCoord current     = id2Coord(local_id);
    TCoord destination = id2Coord(dst_id);

    /*
     * In this direction convention, dir_in == dir_out means immediate
     * physical backtracking.
     */
	//if (local_id != dst_id &&
	//	!isMinimalDirection(dir_in, current, destination, true))
	//	return false;

	if (!isMinimalDirection(dir_out, current, destination, false))
		return false;

	if (dir_in == dir_out)
		return false;

    vector<int> directions;

    int cz = current.z;
    int dz = destination.z;

    int ex = destination.x - current.x;
    int ey = destination.y - current.y;
    int ez = dz - cz;

    if (ez == 0) 
    {
        /*
         * Same-plane movement:
         * even z-plane => OE0
         * odd  z-plane => OE1
         */
        if (cz % 2 == 0)
            directions = routingOddEven1_DPStrict(current, destination);
        else
            directions = routingOddEven0_DPStrict(current, destination);
    }
    else if (ez > 0) { // going DOWN
        if ((ex == 0) && (ey == 0)) {
            directions.push_back(DIRECTION_DOWN);
        }
        else {
          /*
             * The router permits in-plane routing on odd z planes, and
             * additionally on the true source plane. DP has no packet-source
             * state, so it keeps the source-independent strict subset:
             * odd z planes only.
             *
             * Odd z planes use OE0: Y-primary / row-wise.
             */
            if (cz % 2 == 1 || dir_in!= DIRECTION_UP)
            {
              if (cz % 2 == 0)
                  directions = routingOddEven1_DPStrict(current, destination);
              else
                  directions = routingOddEven0_DPStrict(current, destination);
            }
            //else
            if ((dz % 2 == 1) || (ez > 1))
                directions.push_back(DIRECTION_DOWN);
        }
    }
    else { // ez < 0, going UP
        /*
         * Same vertical exclusivity as the router:
         * unaligned + even z-plane => in-plane OE1 only;
         * otherwise => UP only.
         */
        if ((ex != 0 || ey != 0) && (cz % 2 == 0))
            directions = routingOddEven1_DPStrict(current, destination);
        //else
            directions.push_back(DIRECTION_UP);
    }

    for (unsigned int i = 0; i < directions.size(); i++) {
        if (dir_out == directions[i])
            return true;
    }

    return false;
}

// Check if the direction is a minimal direction towards the destination.
bool DPNode::isMinimalDirection(int dir,
                                const TCoord& current,
                                const TCoord& destination,
                                bool incoming)
{
    switch (dir) {
    case DIRECTION_EAST:
        if (incoming)
            return destination.x <= current.x;  // came from east, moved west
        else
            return destination.x > current.x;   // go east

    case DIRECTION_WEST:
        if (incoming)
            return destination.x >= current.x;  // came from west, moved east
        else
            return destination.x < current.x;   // go west

    case DIRECTION_SOUTH:
        if (incoming)
            return destination.y <= current.y;  // came from south, moved north
        else
            return destination.y > current.y;   // go south

    case DIRECTION_NORTH:
        if (incoming)
            return destination.y >= current.y;  // came from north, moved south
        else
            return destination.y < current.y;   // go north

    case DIRECTION_UP:
        if (incoming)
            return destination.z <= current.z;  // came from up, moved down
        else
            return destination.z < current.z;   // go up

    case DIRECTION_DOWN:
        if (incoming)
            return destination.z >= current.z;  // came from down, moved up
        else
            return destination.z > current.z;   // go down

    default:
        return false;
    }
}
vector<int> DPNode::routingOddEvenDPStrict(const TCoord& current,
                                           const TCoord& destination)
{
    vector<int> directions;

    int c0 = current.x;
    int c1 = current.y;

    int d0 = destination.x;
    int d1 = destination.y;

    int e0 = d0 - c0;
    int e1 = -(d1 - c1);

    if (e0 == 0) {
        if (e1 > 0)
            directions.push_back(DIRECTION_NORTH);
        else if (e1 < 0)
            directions.push_back(DIRECTION_SOUTH);
    }
    else if (e0 > 0) { // destination is EAST
        if (e1 == 0) {
            directions.push_back(DIRECTION_EAST);
        }
        else {
            /*
             * Original source-sensitive condition:
             *     (c0 % 2 == 1) || (c0 == s0)
             *
             * DP does not know true source column, so remove c0 == s0.
             */
            if (c0 % 2 == 1) {
                if (e1 > 0)
                    directions.push_back(DIRECTION_NORTH);
                else
                    directions.push_back(DIRECTION_SOUTH);
            }

            if ((d0 % 2 == 1) || (e0 != 1))
                directions.push_back(DIRECTION_EAST);
        }
    }
    else { // e0 < 0, destination is WEST
        directions.push_back(DIRECTION_WEST);

        if (c0 % 2 == 0) {
            if (e1 > 0)
                directions.push_back(DIRECTION_NORTH);
            else if (e1 < 0)
                directions.push_back(DIRECTION_SOUTH);
        }
    }

    return directions;
}

vector<int> DPNode::routingOddEven0_DPStrict(const TCoord& current,
                                             const TCoord& destination)
{
    vector<int> directions;

    int c0 = current.x;
    int c1 = current.y;

    int d0 = destination.x;
    int d1 = destination.y;

    /*
     * OE0 / row-wise orientation.
     *
     * Same convention as routingOddEven0():
     *   e0 > 0 => destination is WEST
     *   e0 < 0 => destination is EAST
     *   e1 > 0 => destination is SOUTH
     *   e1 < 0 => destination is NORTH
     */
    int e0 = -(d0 - c0);
    int e1 = d1 - c1;

    if (e1 == 0) {
        if (e0 > 0)
            directions.push_back(DIRECTION_WEST);
        else if (e0 < 0)
            directions.push_back(DIRECTION_EAST);
    }
    else if (e1 > 0) { // destination is SOUTH
        if (e0 == 0) {
            directions.push_back(DIRECTION_SOUTH);
        }
        else {
            /*
             * Original source-sensitive condition:
             *     (c1 % 2 == 1) || (c1 == s1)
             *
             * DP does not know true source row, so remove c1 == s1.
             */
            if (c1 % 2 == 1) {
                if (e0 > 0)
                    directions.push_back(DIRECTION_WEST);
                else
                    directions.push_back(DIRECTION_EAST);
            }

            if ((d1 % 2 == 1) || (e1 != 1))
                directions.push_back(DIRECTION_SOUTH);
        }
    }
    else { // e1 < 0, destination is NORTH
        directions.push_back(DIRECTION_NORTH);

        if (c1 % 2 == 0) {
            if (e0 > 0)
                directions.push_back(DIRECTION_WEST);
            else if (e0 < 0)
                directions.push_back(DIRECTION_EAST);
        }
    }

    return directions;
}

vector<int> DPNode::routingOddEven1_DPStrict(
    const TCoord& current,
    const TCoord& destination)
{
    // Current router OE1 is the standard X-primary odd-even algorithm.
    // DP uses its source-independent strict form.
    return routingOddEvenDPStrict(current, destination);
}

// DPNode.cpp
bool DPNode::can_turnFullyAdaptive(int dir_in, int dir_out, int dst_id)
{
    TCoord current     = id2Coord(local_id);
    TCoord destination = id2Coord(dst_id);

    // Reject immediate physical backtracking.
    if (dir_in == dir_out)
        return false;
  
  return isMinimalDirection(dir_out, current, destination, false);

}
