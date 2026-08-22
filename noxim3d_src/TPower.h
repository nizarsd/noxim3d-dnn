/*****************************************************************************

  TPower.h -- Power model

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
#ifndef __TPOWER_H__
#define __TPOWER_H__

// ---------------------------------------------------------------------------
/*
The average energy dissipated by a flit for a hop switch was estimated
as being 0.151nJ, 0.178nJ, 0.182nJ and 0.189nJ for XY, Odd-Even, DyAD,
and NoP-OE respectively

We assumed the tile size to be 2mm x 2mm and that the tiles were
arranged in a regular fashion on the floorplan. The load wire
capacitance was set to 0.50fF per micron, so considering an average of
25% switching activity the amount of energy consumed by a flit for a
hop interconnect is 0.384nJ.
*/

/*
#define PWR_ROUTING                 2*2.36e-12//0.151e-10
#define PWR_ROUTING_XY              PWR_ROUTING    
#define PWR_ROUTING_WEST_FIRST      PWR_ROUTING 
#define PWR_ROUTING_NORTH_LAST      PWR_ROUTING 
#define PWR_ROUTING_NEGATIVE_FIRST  PWR_ROUTING 
#define PWR_ROUTING_ODD_EVEN        PWR_ROUTING 
#define PWR_ROUTING_DYAD            PWR_ROUTING
 
// Added by Ra'ed
#define PWR_ROUTING_FULLY_ADAPTIVE  PWR_ROUTING 
#define PWR_ROUTING_XYZ             PWR_ROUTING 
 
#define PWR_ROUTING_TABLE_BASED     PWR_ROUTING 

#define PWR_SEL_RANDOM              0
#define PWR_SEL_BUFFER_LEVEL        0
#define PWR_SEL_NOP                 0
#define PWR_SEL_DP                  0

#define PWR_FORWARD_FLIT           5*2.1167e-011//0.384e-9//  //(i/p buffer read+ crossbar+ sw arbiter)
#define PWR_LINK                   5.1000e-012
#define PWR_V_LINK            	   3*(3.7177e-013 + 2.1167e-011) //(3.7177e-013 + 0.384e-9/3)//  // (vertical link + forward)   

#define PWR_CORE_FLIT              0
// Added by Ra'ed
#define PWR_KILLING_FLIT           0

#define PWR_INCOMING              5*2.5272e-012 //  0.002e-9//
#define PWR_CLOCKING              1.2924e-011/5 //  0 //
#define PWR_STANDBY               1.2628e-011/5 // 0.0001e-9/2.0 //
*/

#define PWR_ROUTING_XY             0.151e-9
#define PWR_ROUTING_XYZ            0.151e-9
#define PWR_ROUTING_WEST_FIRST     0.155e-9
#define PWR_ROUTING_NORTH_LAST     0.155e-9
#define PWR_ROUTING_NEGATIVE_FIRST 0.155e-9
#define PWR_ROUTING_ODD_EVEN       0.178e-9
#define PWR_ROUTING_DYAD           0.182e-9
#define PWR_ROUTING_FULLY_ADAPTIVE 0.0
#define PWR_ROUTING_TABLE_BASED    0.185e-9

#define PWR_SEL_RANDOM             0.002e-9
#define PWR_SEL_BUFFER_LEVEL       0.006e-9
#define PWR_SEL_NOP                0.012e-9
#define PWR_SEL_DP                 0.012e-9


#define PWR_FORWARD_FLIT           0.384e-9
#define PWR_INCOMING               0.002e-9
#define PWR_STANDBY                0.0001e-9/2.0

#define PWR_CLOCKING               0 //1.2924e-011 
#define PWR_LINK                   5.1000e-012
#define PWR_V_LINK 		   3.7177e-013	
#define PWR_CORE_FLIT              PWR_FORWARD_FLIT

// Added by Ra'ed
#define PWR_KILLING_FLIT           0
#define PWR_INCOMING              0.002e-9//
#define PWR_CLOCKING              1.2924e-011 //
#define PWR_STANDBY               1.2628e-011 // 0.0001e-9/2.0 //




/*
#define PWR_ROUTING                 5*2.36e-12//0.151e-10
#define PWR_ROUTING_XY              PWR_ROUTING    
#define PWR_ROUTING_WEST_FIRST      PWR_ROUTING 
#define PWR_ROUTING_NORTH_LAST      PWR_ROUTING 
#define PWR_ROUTING_NEGATIVE_FIRST  PWR_ROUTING 
#define PWR_ROUTING_ODD_EVEN        PWR_ROUTING 
#define PWR_ROUTING_DYAD            PWR_ROUTING
 
// Added by Ra'ed
#define PWR_ROUTING_FULLY_ADAPTIVE  PWR_ROUTING 
#define PWR_ROUTING_XYZ             PWR_ROUTING 
 
#define PWR_ROUTING_TABLE_BASED     PWR_ROUTING 

#define PWR_SEL_RANDOM              0
#define PWR_SEL_BUFFER_LEVEL        0
#define PWR_SEL_NOP                 0
#define PWR_SEL_DP                  0

#define PWR_FORWARD_FLIT           2.1167e-010//0.384e-9//  //(i/p buffer read+ crossbar+ sw arbiter)
#define PWR_LINK                   5.1000e-011
#define PWR_V_LINK            	   5*(3.7177e-013 + 2.1167e-011) //(3.7177e-013 + 0.384e-9/3)//  // (vertical link + forward)   

#define PWR_CORE_FLIT              0
// Added by Ra'ed
#define PWR_KILLING_FLIT           0

#define PWR_INCOMING              2.5272e-011 //  0.002e-9//
#define PWR_CLOCKING              1.2924e-011/10 //  0 //
#define PWR_STANDBY               1.2628e-011/10 // 0.0001e-9/2.0 //
*/

class TPower
{

 public:

  TPower();

  void Routing();
  void Selection();
  void Standby();
  void Forward();
  void Core();
  void Incoming();
  void Clocking();
  void Link();
  void Vlink();
  void Killing(const TKillFlit& kill_flit);

  double getPower() { return pwr; }
  double getPowerCore() { return p_core; }
  double getPower_aborted_flits () { return pwr_aborted_flits; }

  double getPwrRouting()   { return pwr_routing;   }
  double getPwrSelection() { return pwr_selection; }
  double getPwrForward()   { return pwr_forward;   }
  double getPwrCore()      { return pwr_core;      }  // added by Ra'ed
  double getPwrKilling()   { return pwr_killing;   } // added by Ra'ed
  double getPwrClocking()  { return pwr_clocking;  } // added by Ra'ed
  double getPwrStandBy()   { return pwr_standby;   }
  double getPwrIncoming()  { return pwr_incoming;  }

 private:

  double pwr_routing;
  double pwr_selection;
  double pwr_forward;
  double pwr_link;
  double pwr_vlink; 
  double pwr_core;
  double pwr_killing;
  double pwr_standby;
  double pwr_incoming;
  double pwr_clocking;
  double pwr, pwr_aborted_flits, p_core;
};

// ---------------------------------------------------------------------------

#endif


