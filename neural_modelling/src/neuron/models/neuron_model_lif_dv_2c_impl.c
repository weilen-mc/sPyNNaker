#include "neuron_model_lif_dv_2c_impl.h"

#include <debug.h>

// simple Leaky I&F ODE + dV/dt
static inline void _lif_neuron_closed_form(
        neuron_pointer_t neuron, REAL V_prev, input_t input_this_timestep) {

    REAL alpha = input_this_timestep * neuron->R_membrane + neuron->V_rest;

    // update membrane voltage
    neuron->V_membrane = alpha - (neuron->exp_TC * (alpha - V_prev));


}

void neuron_model_set_global_neuron_params(
        global_neuron_params_pointer_t params) {
    use(params);

    // Does Nothing - no params
}

void update_dv_dt(neuron_pointer_t neuron){
    // voltage change this step
    neuron->dV_dt = neuron->V_membrane - neuron->V_prev;
    neuron->V_prev = neuron->V_membrane;

    // voltage change - filtered
    neuron->dV_dt_slow = ((neuron->dV_dt_slow)*(neuron->gamma)) + \
                         ((neuron->dV_dt)*(neuron->gamma_complement));

   // log_info("V, dv, dvs  = %11.6k, %11.6k, %11.6k",
           // neuron->V_membrane, neuron->dV_dt, neuron->dV_dt_slow);
}

state_t neuron_model_state_update(
        uint16_t num_excitatory_inputs, input_t* exc_input,
        uint16_t num_inhibitory_inputs, input_t* inh_input,
        input_t external_bias,
        neuron_pointer_t neuron) {


    // If outside of the refractory period
    if (neuron->refract_timer <= 0) {

        // Get the input in nA
        input_t input_this_timestep = exc_input[0] - inh_input[0] + \
            external_bias + neuron->I_offset;

        _lif_neuron_closed_form(
            neuron, neuron->V_membrane, input_this_timestep);

        if(neuron->V_membrane >= neuron->V_max){
            neuron->V_membrane = neuron->V_max;
        }
        
        
    } else {
        if((neuron->refract_timer) < (neuron->T_refract)){
            neuron->V_membrane = neuron->V_reset;
        }
        // countdown refractory timer
        neuron->refract_timer -= 1;
        
        // neuron->V2_membrane = 0.0k;
    }

    // todo: this should be done in an event-based manner, with a LUT
    neuron->V2_membrane = exc_input[1] - inh_input[1];
        
    update_dv_dt(neuron);

    // log_info("V, dvS, V2  = %11.6k, %11.6k, %11.6k",
        // neuron->V_membrane, neuron->dV_dt_slow, neuron->V2_membrane );

    return neuron->V_membrane;
}

void neuron_model_has_spiked(neuron_pointer_t neuron) {
//    log_info("post_spiked!");
    // reset membrane voltage
//    neuron->V_membrane = neuron->V_reset;
    if (neuron->refract_timer <= 0){
        neuron->V_membrane = neuron->V_spike;
    // reset refractory timer
        neuron->refract_timer  = neuron->T_refract;
    }

}

state_t neuron_model_get_membrane_voltage(neuron_pointer_t neuron) {
    return neuron->V_membrane;
}

void neuron_model_print_state_variables(restrict neuron_pointer_t neuron) {
    log_debug("V membrane    = %11.4k mv", neuron->V_membrane);
}

void neuron_model_print_parameters(restrict neuron_pointer_t neuron) {
    log_debug("V reset       = %11.4k mv", neuron->V_reset);
    log_debug("V rest        = %11.4k mv", neuron->V_rest);

    log_debug("I offset      = %11.4k nA", neuron->I_offset);
    log_debug("R membrane    = %11.4k Mohm", neuron->R_membrane);

    log_debug("exp(-ms/(RC)) = %11.4k [.]", neuron->exp_TC);

    log_debug("T refract     = %u timesteps", neuron->T_refract);
    log_debug("gamma = %11.4k", neuron->gamma);
    log_debug("gamma_complement = %11.4k", neuron->gamma_complement);
}