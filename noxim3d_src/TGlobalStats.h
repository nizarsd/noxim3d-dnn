/*****************************************************************************

  TGlobalStats.h -- Global Statistics definition

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
#ifndef __TGLOBAL_STATS_H__
#define __TGLOBAL_STATS_H__

//---------------------------------------------------------------------------

#include <iostream>
#include <vector>
#include "TNoC.h"
#include "TTile.h"

//---------------------------------------------------------------------------

class TGlobalStats
{
public:
  TGlobalStats(const TNoC* _noc);
  
  // Returns the aggragated average delay (cycles)
  double getAverageDelay();
  
  // Return Total aborted flits // Modification made by Ra'ed in April
  
  unsigned int getTotalAbortedFlits();
  
  // Return Total aborted packets // Modification made by Ra'ed in April
  
  unsigned int getTotalAbortedPackets();
  
  // Returns the aggragated average delay (cycles) for communication
  // src_id->dst_id
  double getAverageDelay(const int src_id, const int dst_id);

  // Returns the max delay
  double getMaxDelay();

  // Prints pooled per-packet delay percentiles.  Reporting only.
  void showDelayPercentiles(std::ostream& out);

  // Returns the max delay (cycles) experimented by destination
  // node_id. Returns -1 if node_id is not destination of any
  // communication
  double getMaxDelay(const int node_id);
  
   // Returns the average delay (cycles) experimented by destination
  // node_id. Returns -1 if node_id is not destination of any
  // communication - Added by Ra'ed
  double getAverageDelay(const int node_id);

  // Returns the max delay (cycles) for communication src_id->dst_id
  double getMaxDelay(const int src_id, const int dst_id);
  
  // Returns tha matrix of max delay for any node of the network
  vector<vector<double> > getMaxDelayMtx();
  
  // Returns tha matrix of average delay for any node of the network - added by Ra'ed
  vector<vector<double> > getAverageDelayMtx();

  // Returns the aggragated average throughput (flits/cycles)
  double getAverageThroughput();

  // Returns the aggragated average throughput (flits/cycles) for
  // communication src_id->dst_id
  double getAverageThroughput(const int src_id, const int dst_id);
  
     // Returns the average throughput (cycles) experimented by destination
  // node_id. Returns -1 if node_id is not destination of any
  // communication - Added by Ra'ed
  double getAverageThroughput(const int node_id);
  
    // Returns tha matrix of average throughput for any node of the network - added by Ra'ed
  vector<vector<double> > getAverageThroughputMtx();

  // Returns the total number of received packets
  unsigned int getReceivedPackets();

  // Returns the total number of received flits
  unsigned int getReceivedFlits();

  // Returns the maximum value of the accepted traffic
  double getThroughput();

  // Returns the number of routed flits for each router
  vector<vector<unsigned long> > getRoutedFlitsMtx();

  // Returns the total power
  double getPower();
  
    // Returns the total wasted power for aborted flits
  double getPower_aborted_flits();

  // Shows global statistics
  void showStats(std::ostream& out = std::cout, bool detailed = false);
// <Nizar>
  void showStats2();

#ifdef TESTING
  unsigned int drained_total;
#endif

private:
  const TNoC* noc;
};

#endif

