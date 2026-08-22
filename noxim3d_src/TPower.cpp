/*****************************************************************************

  TPower.cpp -- Power model

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
#include <cassert>
#include "NoximDefs.h"
#include "TPower.h"

using namespace std;

// ---------------------------------------------------------------------------

TPower::TPower()
{
  pwr = 0.0;
  pwr_aborted_flits=0.0;
  p_core=0.0;

  pwr_standby  = PWR_STANDBY;
  pwr_forward  = PWR_FORWARD_FLIT;
  pwr_killing  = PWR_KILLING_FLIT;
  pwr_incoming = PWR_INCOMING;
  pwr_clocking = PWR_CLOCKING;
  pwr_core     = PWR_CORE_FLIT;
  pwr_vlink     = PWR_V_LINK; // Nizar
  pwr_link     = PWR_LINK;

  if (TGlobalParams::routing_algorithm == ROUTING_XY && TGlobalParams::mesh_dim_z == 1) pwr_routing = PWR_ROUTING_XY;
  else if (TGlobalParams::routing_algorithm == ROUTING_WEST_FIRST) pwr_routing = PWR_ROUTING_WEST_FIRST;
  else if (TGlobalParams::routing_algorithm == ROUTING_NORTH_LAST) pwr_routing = PWR_ROUTING_NORTH_LAST;
  else if (TGlobalParams::routing_algorithm == ROUTING_NEGATIVE_FIRST) pwr_routing = PWR_ROUTING_NEGATIVE_FIRST;
  else if (TGlobalParams::routing_algorithm == ROUTING_NEGATIVE_FIRST_NM) pwr_routing = PWR_ROUTING_XYZ;
  else if (TGlobalParams::routing_algorithm == ROUTING_ODD_EVEN) pwr_routing = PWR_ROUTING_ODD_EVEN;
  else if (TGlobalParams::routing_algorithm == ROUTING_DYAD) pwr_routing = PWR_ROUTING_DYAD;
  else if (TGlobalParams::routing_algorithm == ROUTING_FULLY_ADAPTIVE) pwr_routing = PWR_ROUTING_FULLY_ADAPTIVE;
  else if (TGlobalParams::routing_algorithm == ROUTING_TABLE_BASED) pwr_routing = PWR_ROUTING_TABLE_BASED;
  else if (TGlobalParams::routing_algorithm == ROUTING_XY && TGlobalParams::mesh_dim_z > 1) pwr_routing = PWR_ROUTING_XYZ;
  else if (TGlobalParams::routing_algorithm == ROUTING_DW_XYZ) pwr_routing = PWR_ROUTING_XYZ;
  else if (TGlobalParams::routing_algorithm == ROUTING_DW_ODD_EVEN) pwr_routing = PWR_ROUTING_XYZ;
  else if (TGlobalParams::routing_algorithm == ROUTING_ODD_EVEN_3DNM) pwr_routing = PWR_ROUTING_XYZ;
  else if (TGlobalParams::routing_algorithm == ROUTING_ODD_EVEN_BALANCED) pwr_routing = PWR_ROUTING_XYZ;
 
  else assert(false);

  if (TGlobalParams::selection_strategy == SEL_RANDOM) pwr_selection = PWR_SEL_RANDOM;
  else if (TGlobalParams::selection_strategy == SEL_BUFFER_LEVEL) pwr_selection = PWR_SEL_BUFFER_LEVEL;
  else if (TGlobalParams::selection_strategy == SEL_NOP) pwr_selection = PWR_SEL_NOP;
  else if (TGlobalParams::selection_strategy == SEL_DP) pwr_selection = PWR_SEL_DP;
  else assert(false);
}

// ---------------------------------------------------------------------------

void TPower::Routing()
{
  pwr += pwr_routing;
}

// ---------------------------------------------------------------------------

void TPower::Selection()
{
  pwr += pwr_selection;
}

// ---------------------------------------------------------------------------

void TPower::Standby()
{
  pwr += pwr_standby;
}

// ---------------------------------------------------------------------------

void TPower::Forward()
{
  pwr += pwr_forward;
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------

void TPower::Core()
{
  p_core += pwr_core;
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------

void TPower::Clocking()
{
  pwr += pwr_clocking;
}

// ---------------------------------------------------------------------------


void TPower::Killing(const TKillFlit& kill_flit)
{
  pwr += pwr_killing;
  double pow=0.0;
  pow= kill_flit.hop_no*(PWR_FORWARD_FLIT + PWR_INCOMING) + kill_flit.flit_age*(PWR_STANDBY+ PWR_ROUTING_FULLY_ADAPTIVE*kill_flit.flit_head);
  pwr_aborted_flits += pwr_killing + pow;
  
 // cout << " power =" << pow << " flit age = " <<kill_flit.flit_age << " kill_flit.flit_head=" << kill_flit.flit_head<<endl; 
}
// ---------------------------------------------------------------------------

void TPower::Incoming()
{
  pwr += pwr_incoming;
}

// ---------------------------------------------------------------------------
void TPower::Link()    // <Nizar> 
{
  pwr += pwr_link;
}

// ---------------------------------------------------------------------------
void TPower::Vlink()    // <Nizar> 
{
  pwr += pwr_vlink;
}

// ---------------------------------------------------------------------------


