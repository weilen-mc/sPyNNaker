#include "neuron_model_lif_erbp_impl.h"

#include <debug.h>

//static inline void _local_error_update()


// simple Leaky I&F ODE
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

state_t neuron_model_state_update(
		uint16_t num_excitatory_inputs, input_t* exc_input,
		uint16_t num_inhibitory_inputs, input_t* inh_input,
		input_t external_bias, neuron_pointer_t neuron, input_t B_t) {
	use(&num_excitatory_inputs);
	use(&num_inhibitory_inputs);

//	log_debug("Exc 1: %12.6k, Exc 2: %12.6k", exc_input[0], exc_input[1]);
//	log_debug("Inh 1: %12.6k, Inh 2: %12.6k", inh_input[0], inh_input[1]);


    // If outside of the refractory period
    if (neuron->refract_timer <= 0) {
		REAL total_exc = exc_input[0];
		REAL total_inh = inh_input[0];

//		for (int i=0; i < num_excitatory_inputs; i++){
//			total_exc += exc_input[i];
//		}
//		for (int i=0; i< num_inhibitory_inputs; i++){
//			total_inh += inh_input[i];
//		}
        // Get the input in nA
        input_t input_this_timestep =
            total_exc - total_inh + external_bias + neuron->I_offset;

        _lif_neuron_closed_form(
            neuron, neuron->V_membrane, input_this_timestep);


    } else {

        // countdown refractory timer
        neuron->refract_timer -= 1;
    }


    REAL total_exc_err = exc_input[1];
    REAL total_inh_err = inh_input[1];

//    neuron->local_err += (total_exc_err - total_inh_err);
    neuron->local_err = neuron->local_err * neuron->exp_TC_err;

    return neuron->V_membrane;
}

void neuron_model_has_spiked(neuron_pointer_t neuron) {

    // reset membrane voltage
    neuron->V_membrane = neuron->V_reset;

    // reset refractory timer
    neuron->refract_timer  = neuron->T_refract;

    neuron->local_err += 1.0k;
}

state_t neuron_model_get_membrane_voltage(neuron_pointer_t neuron) {
    return neuron->V_membrane;
}

void neuron_model_print_state_variables(restrict neuron_pointer_t neuron) {
    log_info("V membrane    = %11.4k mv", neuron->V_membrane);
}

void neuron_model_print_parameters(restrict neuron_pointer_t neuron) {
    log_info("V reset       = %11.4k mv", neuron->V_reset);
    log_info("V rest        = %11.4k mv", neuron->V_rest);

    log_info("I offset      = %11.4k nA", neuron->I_offset);
    log_info("R membrane    = %11.4k Mohm", neuron->R_membrane);

    log_info("exp(-ms/(RC)) = %11.4k [.]", neuron->exp_TC);

    log_info("T refract     = %u timesteps", neuron->T_refract);
}