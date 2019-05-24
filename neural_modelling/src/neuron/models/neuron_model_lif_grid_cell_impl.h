#ifndef _NEURON_MODEL_LIF_CURR_GRID_CELL_IMPL_H_
#define _NEURON_MODEL_LIF_CURR_GRID_CELL_IMPL_H_

#include "neuron_model.h"

/////////////////////////////////////////////////////////////
// definition for LIF neuron parameters
typedef struct neuron_t {
    // membrane voltage [mV]
    REAL     V_membrane;

    // membrane resting voltage [mV]
    REAL     V_rest;

    // membrane resistance [MOhm]
    REAL     R_membrane;

    // 'fixed' computation parameter - time constant multiplier for
    // closed-form solution
    // exp(-(machine time step in ms)/(R * C)) [.]
    REAL     exp_TC;

    // offset current [nA]
    REAL     I_offset;

    // Velocity dependent current
    REAL     I_vel;

    // countdown to end of next refractory period [timesteps]
    int32_t  refract_timer;

    // post-spike reset membrane voltage [mV]
    REAL     V_reset;

    // refractory time of neuron [timesteps]
    int32_t  T_refract;

    // directional preference of neuron
    // 1: N, 2: S, 3: W, 4: E
    int32_t dir_pref;

} neuron_t;

typedef struct global_neuron_params_t {
} global_neuron_params_t;

#endif // _NEURON_MODEL_LIF_CURR_GRID_CELL_IMPL_H_
