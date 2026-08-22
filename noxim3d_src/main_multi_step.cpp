/*****************************************************************************
 
  main.cpp -- The testbench
 
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
 
#include <systemc.h>
#include "NoximDefs.h"
#include "TNoC.h"
#include "TGlobalStats.h"
#include "CmdLineParser.h"
#include <sstream>
using namespace std;
 
#include <unistd.h>
 
 
 
// need to be globally visible to allow "-volume" simulation stop
unsigned int drained_volume;
 
//<Nizar>
void create_ptrace_file(int dz);
void create_floorplan_files(int dx, int dy, int dz);
 
//---------------------------------------------------------------------------
 
// Initialize global configuration parameters (can be overridden with command-line arguments)
int   TGlobalParams::verbose_mode                     = DEFAULT_VERBOSE_MODE;
int   TGlobalParams::trace_mode                       = DEFAULT_TRACE_MODE;
char  TGlobalParams::trace_filename[128]              = DEFAULT_TRACE_FILENAME;
int   TGlobalParams::mesh_dim_x                       = DEFAULT_MESH_DIM_X;
int   TGlobalParams::mesh_dim_y                       = DEFAULT_MESH_DIM_Y;
int   TGlobalParams::mesh_dim_z                       = DEFAULT_MESH_DIM_Z;
int   TGlobalParams::buffer_depth                     = DEFAULT_BUFFER_DEPTH;
int   TGlobalParams::min_packet_size                  = DEFAULT_MIN_PACKET_SIZE;
int   TGlobalParams::max_packet_size                  = DEFAULT_MAX_PACKET_SIZE;
int   TGlobalParams::routing_algorithm                = DEFAULT_ROUTING_ALGORITHM;
char  TGlobalParams::routing_table_filename[128]      = DEFAULT_ROUTING_TABLE_FILENAME;
int   TGlobalParams::selection_strategy               = DEFAULT_SELECTION_STRATEGY;
float TGlobalParams::packet_injection_rate            = DEFAULT_PACKET_INJECTION_RATE;
float TGlobalParams::probability_of_retransmission    = DEFAULT_PROBABILITY_OF_RETRANSMISSION;
int   TGlobalParams::traffic_distribution             = DEFAULT_TRAFFIC_DISTRIBUTION;
char  TGlobalParams::traffic_table_filename[128]      = DEFAULT_TRAFFIC_TABLE_FILENAME;
char  TGlobalParams::traffic_dump_file[128]           = "traffic_rx.csv";
int   TGlobalParams::simulation_time                  = DEFAULT_SIMULATION_TIME;
int   TGlobalParams::stats_warm_up_time               = DEFAULT_STATS_WARM_UP_TIME;
int   TGlobalParams::rnd_generator_seed               = time(NULL);
bool  TGlobalParams::detailed                         = DEFAULT_DETAILED;
float TGlobalParams::dyad_threshold                   = DEFAULT_DYAD_THRESHOLD;
unsigned int TGlobalParams::max_volume_to_be_drained  = DEFAULT_MAX_VOLUME_TO_BE_DRAINED;
 
 
// Thermal management <Nizar>
double   TGlobalParams::t_upper                        =  DEFAULT_T_UPPER ;
double   TGlobalParams::t_lower                        =  DEFAULT_T_LOWER ;              
int      TGlobalParams::dy_t_mode                      =  NO_THROTELLING;            
bool TGlobalParams::pir_gradual			       =  PIR_GRADUAL;
float TGlobalParams::max_Temp 			       = T_AMBIENT;
float TGlobalParams::min_Temp			       = T_AMBIENT;

float TGlobalParams::max_counter		       = 0;
float TGlobalParams::min_counter		       = 0;

// Modification made by Ra'ed in April 2010
int   TGlobalParams::no_of_samples                    = DEFAULT_NO_OF_SAMPLES;
int   TGlobalParams::tcu_interval                     = DEFAULT_TCU_INTERVAL;
int   TGlobalParams::traffic_bin                      = DEFAULT_TRAFFIC_BIN;  // per-router rx binning (CLI: -trafficbin)
int   TGlobalParams::bw_threshold                     = DEFAULT_BW_THRESHOLD;
        
 
vector<pair<int,double> > TGlobalParams::hotspots;
 
//---------------------------------------------------------------------------
// start: added for the Thermal simulation
 
 
 
int sc_main(int arg_num, char* arg_vet[])
{
    // TEMP
drained_volume = 0;
float tile_power;  
char temp[50];
ofstream fout;
ifstream fin;

 
 
// Handle command-line arguments
  parseCmdLine(arg_num, arg_vet);
 
//do this after binding the line arguments
int dx=TGlobalParams::mesh_dim_x;
int dy=TGlobalParams::mesh_dim_y;
int dz=TGlobalParams::mesh_dim_z;
 
 // Signals
 sc_clock        clock("clock", 1, SC_NS);
 sc_clock        dp_clock("dp_clock", 1, SC_NS);
 sc_signal<bool> reset;
 
  // NoC instance
  TNoC* n = new TNoC("NoC");
  n->clock(clock);
  n->dp_clock(dp_clock);
  n->reset(reset);
 
  // Trace signals
  sc_trace_file* tf = NULL;
  if(TGlobalParams::trace_mode)
  {
    tf = sc_create_vcd_trace_file(TGlobalParams::trace_filename);
    sc_trace(tf, reset, "reset");
    sc_trace(tf, clock, "clock");
 
   for(int k=0; k<dz; k++)
    for(int i=0; i<dx; i++)
 
    {
      for(int j=0; j<dy; j++)
      {
        char label[30];
 
        sprintf(label, "req_to_east(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->req_to_east[i][j][k], label);
        sprintf(label, "req_to_west(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->req_to_west[i][j][k], label);
        sprintf(label, "req_to_south(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->req_to_south[i][j][k], label);
        sprintf(label, "req_to_north(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->req_to_north[i][j][k], label);
        sprintf(label, "req_to_up(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->req_to_up[i][j][k], label);
        sprintf(label, "req_to_down(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->req_to_down[i][j][k], label);
 
        sprintf(label, "ack_to_east(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->ack_to_east[i][j][k], label);
        sprintf(label, "ack_to_west(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->ack_to_west[i][j][k], label);
        sprintf(label, "ack_to_south(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->ack_to_south[i][j][k], label);
        sprintf(label, "ack_to_north(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->ack_to_north[i][j][k], label);
        sprintf(label, "ack_to_up(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->ack_to_up[i][j][k], label);
        sprintf(label, "ack_to_down(%02d)(%02d)(%02d)", i, j, k);
        sc_trace(tf, n->ack_to_down[i][j][k], label);
 
      }
    }
  }
 
 
  // Reset the chip and run the simulation and costruct hotspot command 
  reset.write(1);
if (TGlobalParams::verbose_mode!=-2){
  cout << "% Reset..."; }
  srand(TGlobalParams::rnd_generator_seed); // time(NULL));
  sc_start(DEFAULT_RESET_TIME, SC_NS);
  reset.write(0);
if (TGlobalParams::verbose_mode!=-2){  cout << " done! Now running for " << TGlobalParams::simulation_time*TGlobalParams::no_of_samples << " cycles..." << endl;}


   
TGlobalStats ts(n);
int sample;
int Tflits=0;
float desired_pir = TGlobalParams::packet_injection_rate ;
float pir_step=0.002;
//float bwt0;

if (TGlobalParams::pir_gradual)
	TGlobalParams::packet_injection_rate = 0.004;
else
        TGlobalParams::packet_injection_rate = desired_pir;


 // Start the simulation for no. of samples times *********************
for (sample=1; sample <= TGlobalParams::no_of_samples ; sample++)  
    {
    TGlobalParams::probability_of_retransmission=TGlobalParams::packet_injection_rate;
 
      
    /*reset.write(1);
    //srand(TGlobalParams::rnd_generator_seed); // time(NULL));
    sc_start(10, SC_NS);
    reset.write(0); // */
    sc_start(TGlobalParams::simulation_time, SC_NS);  // NoC simulation 

    
    cout<<sample<<" "<<TGlobalParams::packet_injection_rate <<" ";

    ts.showStats2();

	//  DUMPING PIR-DELAY_THROUGHPUT  
	if (TGlobalParams::verbose_mode==-2)
	{
	// cout<<sample<<" "<<TGlobalParams::packet_injection_rate <<" ";
	// ts.showStats2();
	     for (int z=0; z < dz; z++)
		    for(int y=0; y < dy; y++)
		        for(int x=0; x < dx; x++)
			{	
		        //cout << " " <<n->t[x][y][z]->r->stats.chist.size();  //  */
		         n->t[x][y][z]->r->stats.ClearCommHist(); } //  */

			}

	 
    TGlobalParams::packet_injection_rate+=pir_step;

// for resetting stats delay and throughput

        if (TGlobalParams::packet_injection_rate > desired_pir)    
     		TGlobalParams::packet_injection_rate = desired_pir;
}
  // Close the simulation
  if(TGlobalParams::trace_mode) sc_close_vcd_trace_file(tf);
if (TGlobalParams::verbose_mode!=-2){
  cout << endl << "% Noxim3D simulation completed" ; 
  cout << " ( " << sc_time_stamp().to_double()/1000 << " cycles executed)." << endl; }

  // Show statistics
if (TGlobalParams::verbose_mode!=-2){
  TGlobalStats gs(n);
  gs.showStats(std::cout, TGlobalParams::detailed);}
  
  if ((TGlobalParams::max_volume_to_be_drained>0) &&
      (sc_time_stamp().to_double()/1000 >= TGlobalParams::simulation_time))
      {
	  cout << "\nWARNING! the number of flits specified with -volume option"<<endl;
	  cout << "has not been reached. ( " << drained_volume << " instead of " << TGlobalParams::max_volume_to_be_drained << " )" <<endl;
	  cout << "You might want to try an higher value of simulation cycles" << endl;
	  cout << "using -sim option." << endl;
#ifdef TESTING
	  cout << "\n Sum of local drained flits: "  << gs.drained_total << endl;
	  cout << "\n Effective drained volume: " << drained_volume;
#endif
      }
      
      //cout << endl << "% ******************************************************" << endl ;
      

  return 0;

}  
