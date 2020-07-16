#ifndef _NEURON_IMPL_STANDARD_H_
#define _NEURON_IMPL_STANDARD_H_

#include "neuron_impl.h"

// Includes for model parts used in this implementation
#include <neuron/synapse_types/synapse_types_exponential_impl.h>
#include <neuron/models/neuron_model_store_recall_readout_impl.h>
#include <neuron/input_types/input_type_current.h>
#include <neuron/additional_inputs/additional_input_none_impl.h>
#include <neuron/threshold_types/threshold_type_static.h>

// Further includes
#include <common/out_spikes.h>
#include <common/maths-util.h>
#include <recording.h>
#include <debug.h>
#include <random.h>
#include <log.h>

#define V_RECORDING_INDEX 0
#define GSYN_EXCITATORY_RECORDING_INDEX 1
#define GSYN_INHIBITORY_RECORDING_INDEX 2

#ifndef NUM_EXCITATORY_RECEPTORS
#define NUM_EXCITATORY_RECEPTORS 1
#error NUM_EXCITATORY_RECEPTORS was undefined.  It should be defined by a synapse\
       shaping include
#endif

#ifndef NUM_INHIBITORY_RECEPTORS
#define NUM_INHIBITORY_RECEPTORS 1
#error NUM_INHIBITORY_RECEPTORS was undefined.  It should be defined by a synapse\
       shaping include
#endif

//! Array of neuron states
static neuron_pointer_t neuron_array;

//! Input states array
static input_type_pointer_t input_type_array;

//! Additional input array
static additional_input_pointer_t additional_input_array;

//! Threshold states array
static threshold_type_pointer_t threshold_type_array;

//! Global parameters for the neurons
static global_neuron_params_pointer_t global_parameters;

// The synapse shaping parameters
static synapse_param_t *neuron_synapse_shaping_params;

static REAL next_spike_time = 0;
static uint32_t timer = 0;
static uint32_t target_ind = 0;

// Store recall parameters
typedef enum
{
    STATE_IDLE,
    STATE_STORING,
    STATE_STORED,
    STATE_RECALL,
    STATE_SHIFT,
} current_state_t;

uint32_t store_recall_state = STATE_IDLE; // 0: idle, 1: storing, 2:stored, 3:recall
uint32_t stored_value = 0;
uint32_t broacast_value = 0;
REAL ticks_for_mean = 0;

static bool neuron_impl_initialise(uint32_t n_neurons) {

    // allocate DTCM for the global parameter details
    if (sizeof(global_neuron_params_t) > 0) {
        global_parameters = (global_neuron_params_t *) spin1_malloc(
            sizeof(global_neuron_params_t));
        if (global_parameters == NULL) {
            log_error("Unable to allocate global neuron parameters"
                      "- Out of DTCM");
            return false;
        }
    }

    // Allocate DTCM for neuron array
    if (sizeof(neuron_t) != 0) {
        neuron_array = (neuron_t *) spin1_malloc(n_neurons * sizeof(neuron_t));
        if (neuron_array == NULL) {
            log_error("Unable to allocate neuron array - Out of DTCM");
            return false;
        }
    }

    // Allocate DTCM for input type array and copy block of data
    if (sizeof(input_type_t) != 0) {
        input_type_array = (input_type_t *) spin1_malloc(
            n_neurons * sizeof(input_type_t));
        if (input_type_array == NULL) {
            log_error("Unable to allocate input type array - Out of DTCM");
            return false;
        }
    }

    // Allocate DTCM for additional input array and copy block of data
    if (sizeof(additional_input_t) != 0) {
        additional_input_array = (additional_input_pointer_t) spin1_malloc(
            n_neurons * sizeof(additional_input_t));
        if (additional_input_array == NULL) {
            log_error("Unable to allocate additional input array"
                      " - Out of DTCM");
            return false;
        }
    }

    // Allocate DTCM for threshold type array and copy block of data
    if (sizeof(threshold_type_t) != 0) {
        threshold_type_array = (threshold_type_t *) spin1_malloc(
            n_neurons * sizeof(threshold_type_t));
        if (threshold_type_array == NULL) {
            log_error("Unable to allocate threshold type array - Out of DTCM");
            return false;
        }
    }

    // Allocate DTCM for synapse shaping parameters
    if (sizeof(synapse_param_t) != 0) {
        neuron_synapse_shaping_params = (synapse_param_t *) spin1_malloc(
            n_neurons * sizeof(synapse_param_t));
        if (neuron_synapse_shaping_params == NULL) {
            log_error("Unable to allocate synapse parameters array"
                " - Out of DTCM");
            return false;
        }
    }

    // Seed the random input
    validate_mars_kiss64_seed(global_parameters->kiss_seed);

    // Initialise pointers to Neuron parameters in STDP code
//    synapse_dynamics_set_neuron_array(neuron_array);
    log_info("set pointer to neuron array in stdp code");

    return true;
}

static void neuron_impl_add_inputs(
        index_t synapse_type_index, index_t neuron_index,
        input_t weights_this_timestep) {
    // simple wrapper to synapse type input function
    synapse_param_pointer_t parameters =
            &(neuron_synapse_shaping_params[neuron_index]);
    synapse_types_add_neuron_input(synapse_type_index,
            parameters, weights_this_timestep);
}

static void neuron_impl_load_neuron_parameters(
        address_t address, uint32_t next, uint32_t n_neurons) {
    log_debug("reading parameters, next is %u, n_neurons is %u ",
        next, n_neurons);

    //log_debug("writing neuron global parameters");
    spin1_memcpy(global_parameters, &address[next],
            sizeof(global_neuron_params_t));
    next += (sizeof(global_neuron_params_t) + 3) / 4;

    log_debug("reading neuron local parameters");
    spin1_memcpy(neuron_array, &address[next], n_neurons * sizeof(neuron_t));
    next += ((n_neurons * sizeof(neuron_t)) + 3) / 4;

    log_debug("reading input type parameters");
    spin1_memcpy(input_type_array, &address[next],
            n_neurons * sizeof(input_type_t));
    next += ((n_neurons * sizeof(input_type_t)) + 3) / 4;

    log_debug("reading threshold type parameters");
    spin1_memcpy(threshold_type_array, &address[next],
           n_neurons * sizeof(threshold_type_t));
    next += ((n_neurons * sizeof(threshold_type_t)) + 3) / 4;

    log_debug("reading synapse parameters");
    spin1_memcpy(neuron_synapse_shaping_params, &address[next],
           n_neurons * sizeof(synapse_param_t));
    next += ((n_neurons * sizeof(synapse_param_t)) + 3) / 4;

    log_debug("reading additional input type parameters");
        spin1_memcpy(additional_input_array, &address[next],
               n_neurons * sizeof(additional_input_t));
    next += ((n_neurons * sizeof(additional_input_t)) + 3) / 4;

    neuron_model_set_global_neuron_params(global_parameters);

    io_printf(IO_BUF, "\nPrinting global params\n");
    io_printf(IO_BUF, "seed 1: %u \n", global_parameters->kiss_seed[0]);
    io_printf(IO_BUF, "seed 2: %u \n", global_parameters->kiss_seed[1]);
    io_printf(IO_BUF, "seed 3: %u \n", global_parameters->kiss_seed[2]);
    io_printf(IO_BUF, "seed 4: %u \n", global_parameters->kiss_seed[3]);
    io_printf(IO_BUF, "ticks_per_second: %k \n\n", global_parameters->ticks_per_second);
    io_printf(IO_BUF, "prob_command: %k \n\n", global_parameters->prob_command);
    io_printf(IO_BUF, "rate on: %k \n\n", global_parameters->rate_on);
    io_printf(IO_BUF, "rate off: %k \n\n", global_parameters->rate_off);
    io_printf(IO_BUF, "mean 0: %k \n\n", global_parameters->mean_0);
    io_printf(IO_BUF, "mean 1: %k \n\n", global_parameters->mean_1);
    io_printf(IO_BUF, "poisson key: %k \n\n", global_parameters->p_key);
    io_printf(IO_BUF, "poisson pop size: %k \n\n", global_parameters->p_pop_size);


    for (index_t n = 0; n < n_neurons; n++) {
        neuron_model_print_parameters(&neuron_array[n]);
    }

    io_printf(IO_BUF, "size of global params: %u",
    		sizeof(global_neuron_params_t));



    #if LOG_LEVEL >= LOG_DEBUG
        log_debug("-------------------------------------\n");
        for (index_t n = 0; n < n_neurons; n++) {
            neuron_model_print_parameters(&neuron_array[n]);
        }
        log_debug("-------------------------------------\n");
        //}
    #endif // LOG_LEVEL >= LOG_DEBUG
}

static bool neuron_impl_do_timestep_update(index_t neuron_index,
        input_t external_bias, state_t *recorded_variable_values) {

    // Get the neuron itself
    neuron_pointer_t neuron = &neuron_array[neuron_index];

    // Change broadcasted value and state with probability
    // State - 0: idle, 1: storing, 2:stored-idle, 3:recall
    if (timer % 200 == 0 && neuron_index == 2){ //todo check this isn't changing for every neuron
        if (store_recall_state == STATE_RECALL || store_recall_state == STATE_STORING){
            store_recall_state = (store_recall_state + 1) % STATE_SHIFT;
        }
        else{
            REAL random_number = (REAL)(mars_kiss64_seed(global_parameters->kiss_seed) / (REAL)0xffffffff);
            if (random_number < global_parameters->prob_command){
                store_recall_state = (store_recall_state + 1) % STATE_SHIFT;
            }
        }
        REAL switch_value = (REAL)(mars_kiss64_seed(global_parameters->kiss_seed) / (REAL)0xffffffff);
        if (switch_value < 0.5){
            broacast_value = (broacast_value + 1) % 2;
        }
        if (store_recall_state == STATE_STORING){
            stored_value = broacast_value;
        }
        // send packets to the variable poissons with the updated states
        for (int i = 0; i < 4; i++){
            REAL payload = 10;
            if ((broacast_value == i && i < 2) ||
                (i == 2 && store_recall_state == STATE_STORING) ||
                (i == 3 && store_recall_state == STATE_RECALL)){
                payload = global_parameters->rate_on;
            }
            else {
                payload = global_parameters->rate_off;
            }
            for (int j = i*global_parameters->p_pop_size;
                    j < i*global_parameters->p_pop_size + global_parameters->p_pop_size; j++){
                spin1_send_mc_packet(global_parameters->p_key | j, payload, WITH_PAYLOAD);
            }
        }
    }

    // Get the input_type parameters and voltage for this neuron
    input_type_pointer_t input_type = &input_type_array[neuron_index];

    // Get threshold and additional input parameters for this neuron
    threshold_type_pointer_t threshold_type =
    		&threshold_type_array[neuron_index];
    additional_input_pointer_t additional_input =
    		&additional_input_array[neuron_index];
    synapse_param_pointer_t synapse_type =
    		&neuron_synapse_shaping_params[neuron_index];

    // Get the voltage
    state_t voltage = neuron_model_get_membrane_voltage(neuron);


    // Get the exc and inh values from the synapses
    input_t* exc_value = synapse_types_get_excitatory_input(synapse_type);
    input_t* inh_value = synapse_types_get_inhibitory_input(synapse_type);

    // Call functions to obtain exc_input and inh_input
    input_t* exc_input_values = input_type_get_input_value(
           exc_value, input_type, NUM_EXCITATORY_RECEPTORS);
    input_t* inh_input_values = input_type_get_input_value(
           inh_value, input_type, NUM_INHIBITORY_RECEPTORS);

    // Sum g_syn contributions from all receptors for recording
    REAL total_exc = 0;
    REAL total_inh = 0;

    for (int i = 0; i < NUM_EXCITATORY_RECEPTORS-1; i++){
    	total_exc += exc_input_values[i];
    }
    for (int i = 0; i < NUM_INHIBITORY_RECEPTORS-1; i++){
    	total_inh += inh_input_values[i];
    }

    // Call functions to get the input values to be recorded
    recorded_variable_values[GSYN_EXCITATORY_RECORDING_INDEX] = total_exc;
    recorded_variable_values[GSYN_INHIBITORY_RECORDING_INDEX] = total_inh;

    // Call functions to convert exc_input and inh_input to current
    input_type_convert_excitatory_input_to_current(
    		exc_input_values, input_type, voltage);
    input_type_convert_inhibitory_input_to_current(
    		inh_input_values, input_type, voltage);

    external_bias += additional_input_get_input_value_as_current(
    		additional_input, voltage);

    // Reset values after recall
    if (store_recall_state == STATE_IDLE){
        ticks_for_mean = 0;
        global_parameters->mean_0 == 0;
        global_parameters->mean_1 == 0;
        //todo check if readout_V_0/1 need resetting too
    }

    if (neuron_index == 0){
    	recorded_variable_values[V_RECORDING_INDEX] = voltage;
    	// update neuron parameters
    	state_t result = neuron_model_state_update(
    			NUM_EXCITATORY_RECEPTORS, exc_input_values,
				NUM_INHIBITORY_RECEPTORS, inh_input_values,
				external_bias, neuron, -50k);
    	// Finally, set global membrane potential to updated value
    	global_parameters->readout_V_0 = result;

    } else if (neuron_index == 1){
    	recorded_variable_values[V_RECORDING_INDEX] = voltage;
    	// update neuron parameters
    	state_t result = neuron_model_state_update(
    			NUM_EXCITATORY_RECEPTORS, exc_input_values,
				NUM_INHIBITORY_RECEPTORS, inh_input_values,
				external_bias, neuron, -50k);

    	// Finally, set global membrane potential to updated value
    	global_parameters->readout_V_1 = result;
    //&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&//
    //         maybe sign of the error isn't important anymore?         //
    //&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&//
    } else if (neuron_index == 2){ // this is the error source

    	recorded_variable_values[V_RECORDING_INDEX] = stored_value;
    	// Switched to always broadcasting error but with packet
    	if (store_recall_state == STATE_RECALL){ //todo ensure this neuron id is correct
            ticks_for_mean += 1; //todo is it a running error like this over recall?
            // Softmax of the exc and inh inputs representing 1 and 0 respectively
            // may need to scale to stop huge numbers going in the exp
            global_parameters->mean_0 += global_parameters->readout_V_0;
            global_parameters->mean_1 += global_parameters->readout_V_1;
            accum exp_0 = expk(global_parameters->mean_0 / ticks_for_mean);
            accum exp_1 = expk(global_parameters->mean_1 / ticks_for_mean);
            accum softmax_0 = exp_0 / (exp_1 + exp_0);
            accum softmax_1 = exp_1 / (exp_1 + exp_0);
            // What to do if log(0)?
            if (stored_value){
                global_parameters->cross_entropy = -logk(softmax_1);
            }
            else{
                global_parameters->cross_entropy = -logk(softmax_0);
            }
            while (!spin1_send_mc_packet(
                    key | neuron_index,  bitsk(error), 1 )) {
                spin1_delay_us(1);
            }
    	}
        timer++;
    }
//    else if (neuron_index == 3){ // this is the deprecated
//
//    	// Boundary of -0.7 because ln(0.5) =~= -0.7 representing random choice point, > -0.7 is more correct than not
//    	if (global_parameters->cross_entropy < -0.7){
//            // it's incorrect so change doing what you're doing or suppress synapses?
//    	}
//        timer++; // update this here, as needs to be done once per iteration over all the neurons
//    }

    // Shape the existing input according to the included rule
    synapse_types_shape_input(synapse_type);

    #if LOG_LEVEL >= LOG_DEBUG
        neuron_model_print_state_variables(neuron);
    #endif // LOG_LEVEL >= LOG_DEBUG

    // Return the boolean to the model timestep update
    return false;
}

//! \brief stores neuron parameter back into sdram
//! \param[in] address: the address in sdram to start the store
static void neuron_impl_store_neuron_parameters(
        address_t address, uint32_t next, uint32_t n_neurons) {
    log_debug("writing parameters");

    //log_debug("writing neuron global parameters");
    spin1_memcpy(&address[next], global_parameters,
            sizeof(global_neuron_params_t));
    next += (sizeof(global_neuron_params_t) + 3) / 4;

    log_debug("writing neuron local parameters");
    spin1_memcpy(&address[next], neuron_array,
            n_neurons * sizeof(neuron_t));
    next += ((n_neurons * sizeof(neuron_t)) + 3) / 4;

    log_debug("writing input type parameters");
    spin1_memcpy(&address[next], input_type_array,
            n_neurons * sizeof(input_type_t));
    next += ((n_neurons * sizeof(input_type_t)) + 3) / 4;

    log_debug("writing threshold type parameters");
    spin1_memcpy(&address[next], threshold_type_array,
            n_neurons * sizeof(threshold_type_t));
    next += ((n_neurons * sizeof(threshold_type_t)) + 3) / 4;

    log_debug("writing synapse parameters");
    spin1_memcpy(&address[next], neuron_synapse_shaping_params,
            n_neurons * sizeof(synapse_param_t));
    next += ((n_neurons * sizeof(synapse_param_t)) + 3) / 4;

    log_debug("writing additional input type parameters");
    spin1_memcpy(&address[next], additional_input_array,
            n_neurons * sizeof(additional_input_t));
    next += ((n_neurons * sizeof(additional_input_t)) + 3) / 4;
}

#if LOG_LEVEL >= LOG_DEBUG
void neuron_impl_print_inputs(uint32_t n_neurons) {
	bool empty = true;
	for (index_t i = 0; i < n_neurons; i++) {
		empty = empty
				&& (bitsk(synapse_types_get_excitatory_input(
						&(neuron_synapse_shaping_params[i]))
					- synapse_types_get_inhibitory_input(
						&(neuron_synapse_shaping_params[i]))) == 0);
	}

	if (!empty) {
		log_debug("-------------------------------------\n");

		for (index_t i = 0; i < n_neurons; i++) {
			input_t input =
				synapse_types_get_excitatory_input(
					&(neuron_synapse_shaping_params[i]))
				- synapse_types_get_inhibitory_input(
					&(neuron_synapse_shaping_params[i]));
			if (bitsk(input) != 0) {
				log_debug("%3u: %12.6k (= ", i, input);
				synapse_types_print_input(
					&(neuron_synapse_shaping_params[i]));
				log_debug(")\n");
			}
		}
		log_debug("-------------------------------------\n");
	}
}

void neuron_impl_print_synapse_parameters(uint32_t n_neurons) {
	log_debug("-------------------------------------\n");
	for (index_t n = 0; n < n_neurons; n++) {
	    synapse_types_print_parameters(&(neuron_synapse_shaping_params[n]));
	}
	log_debug("-------------------------------------\n");
}

const char *neuron_impl_get_synapse_type_char(uint32_t synapse_type) {
	return synapse_types_get_type_char(synapse_type);
}
#endif // LOG_LEVEL >= LOG_DEBUG

#endif // _NEURON_IMPL_STANDARD_H_