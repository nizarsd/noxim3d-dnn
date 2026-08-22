/*****************************************************************************

  TNoC.cpp -- Network-on-Chip (NoC) implementation

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
#include "TGlobalRoutingTable.h"
#include "TGlobalTrafficTable.h"
#include "TNoC.h"
#include <iomanip>
//---------------------------------------------------------------------------

void TNoC::buildMesh()
{
  // Check for routing table availability
  if (TGlobalParams::routing_algorithm == ROUTING_TABLE_BASED)
    assert(grtable.load(TGlobalParams::routing_table_filename));

  // Check for traffic table availability
  if (TGlobalParams::traffic_distribution == TRAFFIC_TABLE_BASED)
    assert(gttable.load(TGlobalParams::traffic_table_filename));

  // Create the mesh as a matrix of tiles

  for(int i=0; i<TGlobalParams::mesh_dim_x; i++)
    {
      for(int j=0; j<TGlobalParams::mesh_dim_y; j++)
	for(int k=0; k<TGlobalParams::mesh_dim_z; k++)
	{
	  // Create the single Tile with a proper name
	  char tile_name[20];
	  sprintf(tile_name, "Tile[%02d][%02d][%02d]", i, j, k);
	  t[i][j][k] = new TTile(tile_name);

	  // Tell to the router its coordinates
	  t[i][j][k]->r->configure((j*TGlobalParams::mesh_dim_x + i) +
				   (k*TGlobalParams::mesh_dim_x*TGlobalParams::mesh_dim_y),
				   TGlobalParams::stats_warm_up_time,
				   TGlobalParams::buffer_depth,
				   grtable);
	  // Tell to the DP Node its coordinates
	        t[i][j][k]->dp->configure((j*TGlobalParams::mesh_dim_x + i) +
				    (k*TGlobalParams::mesh_dim_x*TGlobalParams::mesh_dim_y));

	  // Tell to the PE its coordinates
	  t[i][j][k]->pe->local_id = (j * TGlobalParams::mesh_dim_x + i)+
				      (k*TGlobalParams::mesh_dim_x*TGlobalParams::mesh_dim_y);
	  t[i][j][k]->pe->stats.configure((j * TGlobalParams::mesh_dim_x + i)+
				      (k*TGlobalParams::mesh_dim_x*TGlobalParams::mesh_dim_y), TGlobalParams::stats_warm_up_time);
          t[i][j][k]->pe->traffic_table = &gttable;  // Needed to choose destination
          t[i][j][k]->pe->never_transmit = (gttable.occurrencesAsSource(t[i][j][k]->pe->local_id) == 0);

	  // Map clock and reset
	  t[i][j][k]->clock(clock);
	  t[i][j][k]->dp_clock(dp_clock);
	  t[i][j][k]->reset(reset);

	  // Map Rx signals
	  t[i][j][k]->req_rx[DIRECTION_NORTH](req_to_south[i][j][k]);
	  t[i][j][k]->flit_rx[DIRECTION_NORTH](flit_to_south[i][j][k]);
	  t[i][j][k]->ack_rx[DIRECTION_NORTH](ack_to_north[i][j][k]);

	  t[i][j][k]->req_rx[DIRECTION_EAST](req_to_west[i+1][j][k]);
	  t[i][j][k]->flit_rx[DIRECTION_EAST](flit_to_west[i+1][j][k]);
	  t[i][j][k]->ack_rx[DIRECTION_EAST](ack_to_east[i+1][j][k]);

	  t[i][j][k]->req_rx[DIRECTION_SOUTH](req_to_north[i][j+1][k]);
	  t[i][j][k]->flit_rx[DIRECTION_SOUTH](flit_to_north[i][j+1][k]);
	  t[i][j][k]->ack_rx[DIRECTION_SOUTH](ack_to_south[i][j+1][k]);

	  t[i][j][k]->req_rx[DIRECTION_WEST](req_to_east[i][j][k]);
	  t[i][j][k]->flit_rx[DIRECTION_WEST](flit_to_east[i][j][k]);
	  t[i][j][k]->ack_rx[DIRECTION_WEST](ack_to_west[i][j][k]);

	  t[i][j][k]->req_rx[DIRECTION_UP](req_to_down[i][j][k]);
	  t[i][j][k]->flit_rx[DIRECTION_UP](flit_to_down[i][j][k]);
	  t[i][j][k]->ack_rx[DIRECTION_UP](ack_to_up[i][j][k]);

	  t[i][j][k]->req_rx[DIRECTION_DOWN](req_to_up[i][j][k+1]);
	  t[i][j][k]->flit_rx[DIRECTION_DOWN](flit_to_up[i][j][k+1]);
	  t[i][j][k]->ack_rx[DIRECTION_DOWN](ack_to_down[i][j][k+1]);

	  // Map Tx signals
	  t[i][j][k]->req_tx[DIRECTION_NORTH](req_to_north[i][j][k]);
	  t[i][j][k]->flit_tx[DIRECTION_NORTH](flit_to_north[i][j][k]);
	  t[i][j][k]->ack_tx[DIRECTION_NORTH](ack_to_south[i][j][k]);

	  t[i][j][k]->req_tx[DIRECTION_EAST](req_to_east[i+1][j][k]);
	  t[i][j][k]->flit_tx[DIRECTION_EAST](flit_to_east[i+1][j][k]);
	  t[i][j][k]->ack_tx[DIRECTION_EAST](ack_to_west[i+1][j][k]);

	  t[i][j][k]->req_tx[DIRECTION_SOUTH](req_to_south[i][j+1][k]);
	  t[i][j][k]->flit_tx[DIRECTION_SOUTH](flit_to_south[i][j+1][k]);
	  t[i][j][k]->ack_tx[DIRECTION_SOUTH](ack_to_north[i][j+1][k]);

	  t[i][j][k]->req_tx[DIRECTION_WEST](req_to_west[i][j][k]);
	  t[i][j][k]->flit_tx[DIRECTION_WEST](flit_to_west[i][j][k]);
	  t[i][j][k]->ack_tx[DIRECTION_WEST](ack_to_east[i][j][k]);

	  t[i][j][k]->req_tx[DIRECTION_UP](req_to_up[i][j][k]);
	  t[i][j][k]->flit_tx[DIRECTION_UP](flit_to_up[i][j][k]);
	  t[i][j][k]->ack_tx[DIRECTION_UP](ack_to_down[i][j][k]);

	  t[i][j][k]->req_tx[DIRECTION_DOWN](req_to_down[i][j][k+1]);
	  t[i][j][k]->flit_tx[DIRECTION_DOWN](flit_to_down[i][j][k+1]);
	  t[i][j][k]->ack_tx[DIRECTION_DOWN](ack_to_up[i][j][k+1]);

	  // Map buffer level signals (analogy with req_tx/rx port mapping) 
	  t[i][j][k]->free_slots[DIRECTION_NORTH](free_slots_to_north[i][j][k]);
	  t[i][j][k]->free_slots[DIRECTION_EAST](free_slots_to_east[i+1][j][k]);
	  t[i][j][k]->free_slots[DIRECTION_SOUTH](free_slots_to_south[i][j+1][k]);
	  t[i][j][k]->free_slots[DIRECTION_WEST](free_slots_to_west[i][j][k]);
	  t[i][j][k]->free_slots[DIRECTION_UP](free_slots_to_up[i][j][k]);
	  t[i][j][k]->free_slots[DIRECTION_DOWN](free_slots_to_down[i][j][k+1]);

	  t[i][j][k]->free_slots_neighbor[DIRECTION_NORTH](free_slots_to_south[i][j][k]);
	  t[i][j][k]->free_slots_neighbor[DIRECTION_EAST](free_slots_to_west[i+1][j][k]);
	  t[i][j][k]->free_slots_neighbor[DIRECTION_SOUTH](free_slots_to_north[i][j+1][k]);
	  t[i][j][k]->free_slots_neighbor[DIRECTION_WEST](free_slots_to_east[i][j][k]);
	  t[i][j][k]->free_slots_neighbor[DIRECTION_UP](free_slots_to_down[i][j][k]);
          t[i][j][k]->free_slots_neighbor[DIRECTION_DOWN](free_slots_to_up[i][j][k+1]);
	  
	  // NoP 
	  t[i][j][k]->NoP_data_out[DIRECTION_NORTH](NoP_data_to_north[i][j][k]);
	  t[i][j][k]->NoP_data_out[DIRECTION_EAST](NoP_data_to_east[i+1][j][k]);
	  t[i][j][k]->NoP_data_out[DIRECTION_SOUTH](NoP_data_to_south[i][j+1][k]);
	  t[i][j][k]->NoP_data_out[DIRECTION_WEST](NoP_data_to_west[i][j][k]);
	  t[i][j][k]->NoP_data_out[DIRECTION_UP](NoP_data_to_up[i][j][k]);
	  t[i][j][k]->NoP_data_out[DIRECTION_DOWN](NoP_data_to_down[i][j][k+1]);

	  t[i][j][k]->NoP_data_in[DIRECTION_NORTH](NoP_data_to_south[i][j][k]);
	  t[i][j][k]->NoP_data_in[DIRECTION_EAST](NoP_data_to_west[i+1][j][k]);
	  t[i][j][k]->NoP_data_in[DIRECTION_SOUTH](NoP_data_to_north[i][j+1][k]);
	  t[i][j][k]->NoP_data_in[DIRECTION_WEST](NoP_data_to_east[i][j][k]);
	  t[i][j][k]->NoP_data_in[DIRECTION_UP](NoP_data_to_down[i][j][k]);
	  t[i][j][k]->NoP_data_in[DIRECTION_DOWN](NoP_data_to_up[i][j][k+1]);
	  
	  // map DP-network 
	  t[i][j][k]->dp_tx[DIRECTION_NORTH] (dp_req_to_north[i][j][k]);
	  t[i][j][k]->dp_tx[DIRECTION_EAST]  (dp_req_to_east [i+1][j][k]);
	  t[i][j][k]->dp_tx[DIRECTION_SOUTH] (dp_req_to_south[i][j+1][k]);
	  t[i][j][k]->dp_tx[DIRECTION_WEST]  (dp_req_to_west [i][j][k]);
	  t[i][j][k]->dp_tx[DIRECTION_UP]    (dp_req_to_up   [i][j][k]);
	  t[i][j][k]->dp_tx[DIRECTION_DOWN]  (dp_req_to_down [i][j][k+1]);

	  t[i][j][k]->dp_rx[DIRECTION_NORTH] (dp_req_to_south[i][j][k]);
	  t[i][j][k]->dp_rx[DIRECTION_EAST]  (dp_req_to_west [i+1][j][k]);
	  t[i][j][k]->dp_rx[DIRECTION_SOUTH] (dp_req_to_north[i][j+1][k]);
	  t[i][j][k]->dp_rx[DIRECTION_WEST]  (dp_req_to_east [i][j][k]);
	  t[i][j][k]->dp_rx[DIRECTION_UP]    (dp_req_to_down [i][j][k]);
	  t[i][j][k]->dp_rx[DIRECTION_DOWN]  (dp_req_to_up   [i][j][k+1]);
  

	}
    }


  // dummy TNoP_data structure
  TNoP_data tmp_NoP;

  tmp_NoP.sender_id = NOT_VALID;

  for (int i=0; i<DIRECTIONS; i++)
  {
      tmp_NoP.channel_status_neighbor[i].free_slots = NOT_VALID;
      tmp_NoP.channel_status_neighbor[i].available = false;
  }

  // Clear signals for borderline nodes
 for(int k=0; k<=TGlobalParams::mesh_dim_z; k++)
  for(int i=0; i<=TGlobalParams::mesh_dim_x; i++)
    {
      req_to_south[i][0][k] = 0;
      ack_to_north[i][0][k] = 0;
      req_to_north[i][TGlobalParams::mesh_dim_y][k] = 0;
      ack_to_south[i][TGlobalParams::mesh_dim_y][k] = 0;
      
      dp_req_to_south[i][0][k] = BIG_VALUE;
      dp_req_to_north[i][TGlobalParams::mesh_dim_y][k] = BIG_VALUE;
       
      free_slots_to_south[i][0][k].write(NOT_VALID);
      free_slots_to_north[i][TGlobalParams::mesh_dim_y][k].write(NOT_VALID);

      NoP_data_to_south[i][0][k].write(tmp_NoP);
      NoP_data_to_north[i][TGlobalParams::mesh_dim_y][k].write(tmp_NoP);

    }
 for(int k=0; k<=TGlobalParams::mesh_dim_z; k++)
  for(int j=0; j<=TGlobalParams::mesh_dim_y; j++)
    {
      req_to_east[0][j][k] = 0;
      ack_to_west[0][j][k] = 0;
      req_to_west[TGlobalParams::mesh_dim_x][j][k] = 0;
      ack_to_east[TGlobalParams::mesh_dim_x][j][k] = 0;
      

       dp_req_to_east[0][j][k] = BIG_VALUE;
       dp_req_to_west[TGlobalParams::mesh_dim_x][j][k] = BIG_VALUE;
	
      free_slots_to_east[0][j][k].write(NOT_VALID);
      free_slots_to_west[TGlobalParams::mesh_dim_x][j][k].write(NOT_VALID);

      NoP_data_to_east[0][j][k].write(tmp_NoP);
      NoP_data_to_west[TGlobalParams::mesh_dim_x][j][k].write(tmp_NoP);

    }

 for(int i=0; i<=TGlobalParams::mesh_dim_x; i++)
  for(int j=0; j<=TGlobalParams::mesh_dim_y; j++)
    {
      req_to_down[i][j][0] = 0;
      ack_to_up[j][j][0] = 0;

      req_to_up[i][j][TGlobalParams::mesh_dim_z] = 0;
      ack_to_down[i][j][TGlobalParams::mesh_dim_z] = 0;

       dp_req_to_down[i][j][0] = BIG_VALUE;
       dp_req_to_up[i][j][TGlobalParams::mesh_dim_z] = BIG_VALUE;

      
      free_slots_to_down[i][j][0].write(NOT_VALID);
      free_slots_to_up[i][j][TGlobalParams::mesh_dim_z].write(NOT_VALID);

      NoP_data_to_down[i][j][0].write(tmp_NoP);
      NoP_data_to_up[i][j][TGlobalParams::mesh_dim_z].write(tmp_NoP);

    }

  // invalidate reservation table entries for non-exhistent channels
 for(int k=0; k<TGlobalParams::mesh_dim_z; k++)
  for(int i=0; i<TGlobalParams::mesh_dim_x; i++)
    {
      t[i][0][k]->r->reservation_table.invalidate(DIRECTION_NORTH);
      t[i][TGlobalParams::mesh_dim_y-1][k]->r->reservation_table.invalidate(DIRECTION_SOUTH);
    }
 for(int k=0; k<TGlobalParams::mesh_dim_z; k++)
  for(int j=0; j<TGlobalParams::mesh_dim_y; j++)
    {
      t[0][j][k]->r->reservation_table.invalidate(DIRECTION_WEST);
      t[TGlobalParams::mesh_dim_x-1][j][k]->r->reservation_table.invalidate(DIRECTION_EAST);
    }

 for(int i=0; i<TGlobalParams::mesh_dim_x; i++)
  for(int j=0; j<TGlobalParams::mesh_dim_y; j++)
    {
      t[i][j][0]->r->reservation_table.invalidate(DIRECTION_UP);
      t[i][j][TGlobalParams::mesh_dim_z-1]->r->reservation_table.invalidate(DIRECTION_DOWN);
    }

}

//---------------------------------------------------------------------------

TTile* TNoC::searchNode(const int id) const
{
 for(int k=0; k<TGlobalParams::mesh_dim_z; k++)
  for (int i=0; i<TGlobalParams::mesh_dim_x; i++)
    for (int j=0; j<TGlobalParams::mesh_dim_y; j++)
      if (t[i][j][k]->r->local_id == id)
	return t[i][j][k];

  return nullptr;
}
//---------------------------------------------------------------------------

//----------------------------------------------------------added by Ra'ed
void TNoC::updateTrafficCounters()
{
  int stime = (int) (sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);
  bool DWflag =(stime%TGlobalParams::tcu_interval==0) && (TGlobalParams::routing_algorithm == ROUTING_DW_XYZ);  
  bool Tflag =(stime%(TGlobalParams::simulation_time+5) == 0);  
  int  tot_count[TGlobalParams::mesh_dim_x][TGlobalParams::mesh_dim_y];

/*// free  slots
if(stime>0)
{
float avbf=0.0;

//for(int k=0; k<TGlobalParams::mesh_dim_z; k++)
//      for (int j=0; j<TGlobalParams::mesh_dim_y; j++)
//	      for (int i=0; i<TGlobalParams::mesh_dim_x; i++)
//		  for (int d=0; d<DIRECTIONS; d++) 
			avbf=t[3][3][1]->r->buffer[1].getCurrentFreeSlots();
			int avbf1=t[1][1][1]->r->buffer[3].getCurrentFreeSlots();

cout<<"avbf("<<stime<<")="<< avbf <<";"<<endl; 
cout<<"avbf1("<<stime<<")="<< avbf1 <<";"<<endl; 

}
// */

/*
bool DispFlag =(stime%(TGlobalParams::simulation_time)==0) ;
//bool DispFlag =DWflag ;

if (DispFlag) 
{
cout << stime << " :" ;
for(int k=0; k<TGlobalParams::mesh_dim_z; k++)
      {   
	     cout << endl;
	     for (int j=0; j<TGlobalParams::mesh_dim_y; j++)
   	      {  
   		  cout << "   ";
   		     for (int i=0; i<TGlobalParams::mesh_dim_x; i++)
			   //cout<< setw(5) << t[i][j][k]->r->router_temp << "|" << setw(3) << t[i][j][k]->r->throt_level <<"   "; 
			   cout<< setw(4) <<t[i][j][k]->r->traffic_counter << " | "<< setw(4) << t[i][j][k]->r->current_router_temp<<"   ";
   		     	   cout << endl; 
   	      }
      } 
for(int i=0; i<TGlobalParams::mesh_dim_x; i++)  
	for(int j=0; j<TGlobalParams::mesh_dim_y; j++)  
		for(int k=0; k<TGlobalParams::mesh_dim_z; k++)  
			 t[i][j][k]->r->traffic_counter=0; 

}  // end of printing */


//  if ((DWflag || Tflag ) && (TGlobalParams::mesh_dim_z>1)) 
   if ((DWflag) && (TGlobalParams::mesh_dim_z>1)) 

    {
  	for (int j=0; j<TGlobalParams::mesh_dim_y; j++)
   		 for (int i=0; i<TGlobalParams::mesh_dim_x; i++)
   		     {
   		      int dw=0;
   		      int cnt=t[i][j][TGlobalParams::mesh_dim_z-1]->r->traffic_counter;
   		      for(int k=TGlobalParams::mesh_dim_z-2; k>=0; k--)      
   		      		{
   		      			cnt+=t[i][j][k]->r->traffic_counter;
   		      			if (cnt< TGlobalParams::bw_threshold)
   		      					dw++;
   		      		}
   		      tot_count[i][j]=cnt;
   		      
				if (v_throt_level[i][j]==0)  // dw_level depends on traffic_counter
					for(int k=0; k<TGlobalParams::mesh_dim_z; k++)
							t[i][j][k]->r->dw_level=dw;
				else 
					for(int k=0; k<TGlobalParams::mesh_dim_z; k++) // dw_level depends on throttleing level
							t[i][j][k]->r->dw_level=v_throt_level[i][j];

			 	
				for(int k=0; k<TGlobalParams::mesh_dim_z; k++)  
						 t[i][j][k]->r->traffic_counter=0;    				   			
  			 }      		 
    }  // if flags	
}



// Per-router received-flit dump. Dormant (bit-identical to baseline) unless
// -trafficbin N is given; then every N cycles it writes one CSV row per node
// (cycle,node,flits) and resets each counter so each row is per-bin throughput.
// Run with N >= simulation_time for a single whole-run total (heatmap mode).
void TNoC::dumpTraffic()
{
	if (TGlobalParams::traffic_bin <= 0) return;   // gated: off unless bin specified
	if (reset.read()) return;

	int stime = (int)(sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);
	if (stime < 0 || (stime % TGlobalParams::traffic_bin) != 0) return;

	if (!traffic_csv.is_open()) {
		traffic_csv.open(TGlobalParams::traffic_dump_file);
		traffic_csv << "cycle,node,flits\n";
	}

	for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
		for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
			for (int x=0; x<TGlobalParams::mesh_dim_x; x++) {
				TCoord c; c.x=x; c.y=y; c.z=z;
				traffic_csv << stime << ',' << coord2Id(c) << ','
				            << t[x][y][z]->r->rx_flit_counter << '\n';
				t[x][y][z]->r->rx_flit_counter = 0;   // reset for next bin
			}
	traffic_csv.flush();
	last_traffic_stime = stime;
}

// Flush the final partial bin: dumpTraffic only fires on bin boundaries, so
// flits received after the last boundary would otherwise be dropped. Call once
// from main() after sc_start returns (a timed sc_start does not invoke the
// SystemC end_of_simulation callback).
void TNoC::flushTraffic()
{
	if (TGlobalParams::traffic_bin <= 0) return;

	int stime = (int)(sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);
	if (stime == last_traffic_stime) { if (traffic_csv.is_open()) traffic_csv.close(); return; }

	if (!traffic_csv.is_open()) {
		traffic_csv.open(TGlobalParams::traffic_dump_file);
		traffic_csv << "cycle,node,flits\n";
	}
	for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
		for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
			for (int x=0; x<TGlobalParams::mesh_dim_x; x++) {
				TCoord c; c.x=x; c.y=y; c.z=z;
				traffic_csv << stime << ',' << coord2Id(c) << ','
				            << t[x][y][z]->r->rx_flit_counter << '\n';
				t[x][y][z]->r->rx_flit_counter = 0;
			}
	traffic_csv.flush();
	traffic_csv.close();
}

void TNoC::dy_dp_manage()
{
	int dx=TGlobalParams::mesh_dim_x;
	int dy=TGlobalParams::mesh_dim_y;
	int dz=TGlobalParams::mesh_dim_z;
	float Tr, Cr, tmin, tmax, cmin, cmax, tglevel;
	TCoord pillar;
 int stime = (int) (sc_time_stamp().to_double()/1000 - DEFAULT_RESET_TIME);

 if ((stime%(TGlobalParams::tcu_interval+1) == 0) ) //update min and max traffic_counter
	{ 
		cmax=0.0;
		cmin=t[0][0][0]->r->traffic_counter;

		for (int x=0; x<dx; x++)
			for(int y=0; y<dy; y++)
				for(int z=0; z<dz; z++)
				{
					Cr= t[x][y][z]->r->traffic_counter;

					if ( cmax < Cr)
						cmax=Cr;
					if ( cmin > Cr)
        					cmin=Cr;
				}
	TGlobalParams::max_counter=cmax;
	TGlobalParams::min_counter=cmin;

} // end update min and max traffic_counter



 if ((stime%(TGlobalParams::simulation_time+1) == 0) ) //&&  (TGlobalParams::dy_t_mode==T_MODE_VERTICAL || TGlobalParams::dy_t_mode==T_MODE_GLOBAL))
	{ 
		tmax=0.0;
		tmin=t[0][0][0]->r->router_temp;


		for (int x=0; x<dx; x++)
			for(int y=0; y<dy; y++)
				for(int z=0; z<dz; z++)
				{
					Tr= t[x][y][z]->r->router_temp;
					if ( tmax < Tr)
						tmax=Tr;
					if ( tmin > Tr)
        					tmin=Tr;
				}
	TGlobalParams::max_Temp=tmax;
	TGlobalParams::min_Temp=tmin;


   if (TGlobalParams::dy_t_mode == T_MODE_VERTICAL )
	{	
				for (int x=0; x<dx; x++)
				{
					for(int y=0; y<dy; y++)
					{
						tmax=0.0;
						for(int z=0; z<dz; z++)
						{
							Tr= t[x][y][z]->r->router_temp;
							if ( tmax < Tr)
	 						tmax=Tr;
	      		      	}
	 					pillar.x=x;
						pillar.y=y;
						TAVT(tmax, pillar);  
					}
			   }
	}
 else if (TGlobalParams::dy_t_mode == T_MODE_GLOBAL )
	{
							
				if (tmax >= TGlobalParams::t_upper)
					tglevel=0.0;
				else 
					tglevel=1;
				    
				for (int x=0; x<dx; x++)
					for(int y=0; y<dy; y++)
						for(int z=0; z<dz; z++)
							t[x][y][z]->r->throt_level=tglevel;
				
						
	}
  }        	  
}



// thermal-aware vertical throttling
void TNoC::TAVT(double max_temp, TCoord pillar)
{
	
	if ((max_temp >= TGlobalParams::t_upper))
		{
		if (v_throt_level[pillar.x][pillar.y] < TGlobalParams::mesh_dim_z) {
			v_throt_level[pillar.x][pillar.y]++;
			VT(v_throt_level[pillar.x][pillar.y], pillar);
			}
		}
        else if (max_temp <= TGlobalParams::t_lower)
		{
		if (v_throt_level[pillar.x][pillar.y] >0)
		v_throt_level[pillar.x][pillar.y]--;
		}


VT(v_throt_level[pillar.x][pillar.y], pillar);

}



// thermal-aware vertical throttling
void TNoC::VT(int level, TCoord pillar)
{
	float min_throt_level=0.1;
	int dz=TGlobalParams::mesh_dim_z;

	if (TGlobalParams::routing_algorithm==ROUTING_DW_XYZ && TGlobalParams::routing_algorithm==ROUTING_DW_ODD_EVEN)
		{
		min_throt_level=0.0;
		if(level > TGlobalParams::mesh_dim_z-1)
			level =TGlobalParams::mesh_dim_z-1;
		}

	//assert(level <=dz);
	
       for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
	       	t[pillar.x][pillar.y][z]->r->throt_level=1.0;
	
	if (level>0 && level < dz)
		
		{
		for (int z=0; z<level; z++)
			t[pillar.x][pillar.y][z]->r->throt_level=min_throt_level; // 0

		t[pillar.x][pillar.y][level-1]->r->throt_level=0.5;
	    
		}
	else if (level>0 && level == dz)
	      for (int z=0; z<level-1; z++)
		  t[pillar.x][pillar.y][z]->r->throt_level=min_throt_level; // 0
     
}       


