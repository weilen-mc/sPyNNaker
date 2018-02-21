#ifndef _INPUT_TYPE_CURRENT_H_
#define _INPUT_TYPE_CURRENT_H_

#include "input_type.h"

typedef struct input_type_t {
} input_type_t;

static inline input_t input_type_get_input_value(
        input_t value, input_type_pointer_t input_type) {
    use(input_type);
    return value;
}

static inline input_t input_type_convert_excitatory_input_to_current(
        input_t exc_input, input_type_pointer_t input_type,
        state_t membrane_voltage) {
    use(input_type);
    use(membrane_voltage);
    UFRACT scalar = 0.00028 * 8; // 0.000035 * 2^3 (to account for ring buffer shift being set (statically) to 12)
    return scalar * exc_input;
}

static inline input_t input_type_convert_inhibitory_input_to_current(
        input_t inh_input, input_type_pointer_t input_type,
        state_t membrane_voltage) {
    use(input_type);
    use(membrane_voltage);
    UFRACT scalar = 0.00028 * 8; // 0.000035 * 2^3 (to account for ring buffer shift being set (statically) to 12)
    return scalar * inh_input;
}

#endif // _INPUT_TYPE_CURRENT_H_
