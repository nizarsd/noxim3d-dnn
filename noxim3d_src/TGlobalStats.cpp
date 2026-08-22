/*****************************************************************************

  TGlobalStats.cpp -- Global Statistics implementation

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
#include <iomanip>
#include <algorithm>
#include "TGlobalStats.h"

//---------------------------------------------------------------------------

TGlobalStats::TGlobalStats(const TNoC* _noc)
{
  noc = _noc;

#ifdef TESTING
  drained_total = 0;
#endif
}

//---------------------------------------------------------------------------

double TGlobalStats::getAverageDelay()
{
  unsigned int total_packets = 0;
  double       avg_delay     = 0.0;

for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
      {
	unsigned int received_packets = noc->t[x][y][z]->r->stats.getReceivedPackets(); 

	if (received_packets)
	  {
	    avg_delay += received_packets * noc->t[x][y][z]->r->stats.getAverageDelay();
	    total_packets += received_packets;
	  }
      }

  avg_delay /= (double)total_packets;

  return avg_delay;  
}


//---------------------------------------------------------------------------

double TGlobalStats::getAverageDelay(const int src_id, const int dst_id)
{
  TTile* tile = noc->searchNode(dst_id);
  
  assert(tile != NULL);

  return tile->r->stats.getAverageDelay(src_id);
}

//---------------------------------------------------------------------------

double TGlobalStats::getMaxDelay()
{
  double maxd = -1.0;
  
for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
      {
	TCoord coord;
	coord.x = x;
	coord.y = y;
	coord.z = z;
	int node_id = coord2Id(coord);
	double d = getMaxDelay(node_id);
	if (d > maxd)
	  maxd = d;
      }

  return maxd;
}
//---------------------------------------------------------------------------

double TGlobalStats::getMaxDelay(const int node_id)
{
  TCoord coord = id2Coord(node_id);

  unsigned int received_packets = noc->t[coord.x][coord.y][coord.z]->r->stats.getReceivedPackets(); 

  if (received_packets)
    return noc->t[coord.x][coord.y][coord.z]->r->stats.getMaxDelay();
  else
    return -1.0;
}

//---------------------------------------------------------------------------
// Added by Ra'ed
//---------------------------------------------------------------------------

double TGlobalStats::getAverageDelay(const int node_id)
{
  TCoord coord = id2Coord(node_id);

  unsigned int received_packets = noc->t[coord.x][coord.y][coord.z]->r->stats.getReceivedPackets(); 

  if (received_packets)
    return noc->t[coord.x][coord.y][coord.z]->r->stats.getAverageDelay();
  else
    return -1.0;
}

//---------------------------------------------------------------------------

double TGlobalStats::getMaxDelay(const int src_id, const int dst_id)
{
  TTile* tile = noc->searchNode(dst_id);
  
  assert(tile != NULL);

  return tile->r->stats.getMaxDelay(src_id);
}

//---------------------------------------------------------------------------

/*vector<vector<double> > TGlobalStats::getMaxDelayMtx()
{
  vector<vector<double> > mtx;

    mtx.resize(TGlobalParams::mesh_dim_y);
    for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
       mtx[y].resize(TGlobalParams::mesh_dim_x);

for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
      {
	TCoord coord;
	coord.x = x;
	coord.y = y;
	coord.z = z;
	int id = coord2Id(coord);
	mtx[z][y][x] = getMaxDelay(id);
      }

  return mtx;
}

//---------------------------------------------------------------------------
// Added by Ra'ed
//---------------------------------------------------./noxim -dimx 10 -dimy 8 -size 16 16 -sim 5000 -pir .03 0 -samp 1 -seed 123------------------------

vector<vector<double> > TGlobalStats::getAverageDelayMtx()
{
  vector<vector<double> > mtx;

  mtx.resize(TGlobalParams::mesh_dim_y);
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    mtx[y].resize(TGlobalParams::mesh_dim_x);
    
for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
      {
	TCoord coord;
	coord.x = x;
	coord.y = y;
	coord.z = z;
	int id = coord2Id(coord);
	mtx[z][y][x] = getAverageDelay(id);
      }

  return mtx;
}
*/
//---------------------------------------------------------------------------

double TGlobalStats::getAverageThroughput(const int src_id, const int dst_id)
{
  TTile* tile = noc->searchNode(dst_id);
  
  assert(tile != NULL);

  return tile->r->stats.getAverageThroughput(src_id);
}

//---------------------------------------------------------------------------

double TGlobalStats::getAverageThroughput()
{
  unsigned int total_comms    = 0;
  double       avg_throughput = 0.0;

for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
      {
	unsigned int ncomms = noc->t[x][y][z]->r->stats.getTotalCommunications(); 

	if (ncomms)
	  {
	    avg_throughput += ncomms * noc->t[x][y][z]->r->stats.getAverageThroughput();
	    total_comms += ncomms;
	  }
      }

  avg_throughput /= (double)total_comms;

  return avg_throughput;
}

//---------------------------------------------------------------------------
// Added by Ra'ed
//---------------------------------------------------------------------------

double TGlobalStats::getAverageThroughput(const int node_id)
{
  TCoord coord = id2Coord(node_id);

  unsigned int received_packets = noc->t[coord.x][coord.y][coord.z]->r->stats.getReceivedPackets(); 

  if (received_packets)
    return noc->t[coord.x][coord.y][coord.z]->r->stats.getAverageThroughput();
  else
    return -1.0;
}

//---------------------------------------------------------------------------

unsigned int TGlobalStats::getReceivedPackets()
{
  unsigned int n = 0;
  
for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
      n += noc->t[x][y][z]->r->stats.getReceivedPackets();

  return n;
}

//---------------------------------------------------------------------------

unsigned int TGlobalStats::getReceivedFlits()
{
  unsigned int n = 0;

for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
    {
       n += noc->t[x][y][z]->r->stats.getReceivedFlits();
#ifdef TESTING
       drained_total+= noc->t[x][y][z]->r->local_drained;
#endif
    }

  return n;
}

//---------------------------------------------------------------------------

double TGlobalStats::getThroughput()
{
  int total_cycles = TGlobalParams::simulation_time*TGlobalParams::no_of_samples - TGlobalParams::stats_warm_up_time;

  //  int number_of_ip = TGlobalParams::mesh_dim_x * TGlobalParams::mesh_dim_y;
  //  return (double)getReceivedFlits()/(double)(total_cycles * number_of_ip);

  unsigned int n   = 0;
  unsigned int trf = 0;
 for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
      {
	unsigned int rf = noc->t[x][y][z]->r->stats.getReceivedFlits();

	if (rf != 0)
	  n++;

	trf += rf;
      }
    //  n=(unsigned int)TGlobalParams::mesh_dim_x * TGlobalParams::mesh_dim_y; // added by Ra'ed
  return (double)trf/(double)(total_cycles * n);

}


//---------------------------------------------------------------------------

double TGlobalStats::getPower()
{
  double power = 0.0;

for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for(int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for(int x=0; x<TGlobalParams::mesh_dim_x; x++)
        power += noc->t[x][y][z]->r->getPower();

  return power;
}


//---------------------------------------------------------------------------

double TGlobalStats::getPower_aborted_flits()
{
  double power_aborted_flits=0.0;

for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
  for(int y=0; y<TGlobalParams::mesh_dim_y; y++)
    for(int x=0; x<TGlobalParams::mesh_dim_x; x++)
       power_aborted_flits += noc->t[x][y][z]->r->getPower_aborted_flits();

  return power_aborted_flits;
}

//---------------------------------------------------------------------------

// Pooled per-packet delay percentiles.  chist[].delays already holds exactly one
// entry per received packet (HEAD flits only, and TStats.cpp discards arrivals
// before warm_up_time), so this is the same population getAverageDelay() and
// getMaxDelay() summarise -- the percentiles are exact, not estimated.
// Reporting only: reads accumulated stats after the run, changes no state.
void TGlobalStats::showDelayPercentiles(std::ostream& out)
{
  vector<double> d;
  for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
    for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
      for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
	{
	  vector<CommHistory>& ch = noc->t[x][y][z]->r->stats.chist;
	  for (unsigned int i=0; i<ch.size(); i++)
	    d.insert(d.end(), ch[i].delays.begin(), ch[i].delays.end());
	}

  if (d.empty()) return;
  sort(d.begin(), d.end());

  const double q[5] = {0.50, 0.90, 0.95, 0.99, 0.999};
  const char*  nm[5] = {"p50", "p90", "p95", "p99", "p99.9"};
  for (int k=0; k<5; k++)
    {
      unsigned int idx = (unsigned int)(q[k]*(d.size()-1) + 0.5);
      out << "% Delay " << nm[k] << " (cycles): " << d[idx] << endl;
    }
  out << "% Delay samples: " << d.size() << endl;
}

//---------------------------------------------------------------------------

void TGlobalStats::showStats(std::ostream& out, bool detailed)
{
  out << "% Total received packets: " << getReceivedPackets() << endl;
  out << "% Total received flits: " << getReceivedFlits() << endl;
  out << "% Global average delay (cycles): " << getAverageDelay() << endl;
  out << "% Global average throughput (flits/cycle): " << getAverageThroughput() << endl;
  out << "% Throughput (flits/cycle/IP): " << getThroughput() << endl;
  out << "% Max delay (cycles): " << getMaxDelay() << endl;
  showDelayPercentiles(out);
  out << "% Total energy (J): " << getPower() << endl;
  
  
  if (detailed)
    {
      out << endl << "detailed = [" << endl;
     for (int z=0; z<TGlobalParams::mesh_dim_z; z++)
      for (int y=0; y<TGlobalParams::mesh_dim_y; y++)
	for (int x=0; x<TGlobalParams::mesh_dim_x; x++)
	  noc->t[x][y][z]->r->stats.showStats((y*TGlobalParams::mesh_dim_x+x)+z*TGlobalParams::mesh_dim_x*TGlobalParams::mesh_dim_y,out,true);
      out << "];" << endl;

    /*  // show MaxDelay matrix
      vector<vector<double> > md_mtx = getMaxDelayMtx();

      out << endl << "max_delay = [" << endl;
      for (unsigned int y=0; y<md_mtx.size(); y++)
	{
	  out << "   ";
	  for (unsigned int x=0; x<md_mtx[y].size(); x++)
	    out << setw(6) << md_mtx[y][x];
	  out << endl;
	}
      out << "];" << endl;
      
      // show AverageDelay matrix
      vector<vector<double> > ad_mtx = getAverageDelayMtx();

      out << endl << "Average_delay = [" << endl;
      for (unsigned int y=0; y<ad_mtx.size(); y++)
	{
	  out << "   ";
	  for (unsigned int x=0; x<ad_mtx[y].size(); x++)
	    out << setw(10) << ad_mtx[y][x];
	  out << endl;
	}
      out << "];" << endl;
      
       // show AverageThroughput matrix
      vector<vector<double> > td_mtx = getAverageThroughputMtx();

      out << endl << "Average_Throughput = [" << endl;
      for (unsigned int y=0; y<td_mtx.size(); y++)
	{
	  out << "   ";
	  for (unsigned int x=0; x<td_mtx[y].size(); x++)
	    out << setw(10) << td_mtx[y][x];
	  out << endl;
	}
      out << "];" << endl;

      // show RoutedFlits matrix
      vector<vector<unsigned long> > rf_mtx = getRoutedFlitsMtx();

      out << endl << "routed_flits = [" << endl;
      for (unsigned int y=0; y<rf_mtx.size(); y++)
	{
	  out << "   ";
	  for (unsigned int x=0; x<rf_mtx[y].size(); x++)
	    out << setw(10) << rf_mtx[y][x];
	  out << endl;
	}
      out << "];" << endl;*/
    }
}

void TGlobalStats::showStats2()
{
  cout << getAverageDelay() << "\t" << getThroughput()*TGlobalParams::no_of_samples << " " << getReceivedFlits() << endl; 
  
 }
//---------------------------------------------------------------------------

