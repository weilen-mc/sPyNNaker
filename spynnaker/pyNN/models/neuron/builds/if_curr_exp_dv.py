from spynnaker.pyNN.models.neuron.neuron_models \
    import NeuronModelLeakyIntegrateAndFireDvDt
from spynnaker.pyNN.models.neuron.synapse_types import SynapseTypeExponential
from spynnaker.pyNN.models.neuron.input_types import InputTypeCurrent
from spynnaker.pyNN.models.neuron.threshold_types import ThresholdTypeStatic
from spynnaker.pyNN.models.neuron import AbstractPopulationVertex

# global objects
DEFAULT_MAX_ATOMS_PER_CORE = 255
_apv_defs = AbstractPopulationVertex.non_pynn_default_parameters


class IFCurrExpDvDt(AbstractPopulationVertex):
    """ Leaky integrate and fire neuron with an exponentially decaying \
        current input
    """

    _model_based_max_atoms_per_core = DEFAULT_MAX_ATOMS_PER_CORE

    default_parameters = {
        'tau_m': 20.0, 'cm': 1.0, 'v_rest': -65.0, 'v_reset': -65.0,
        'v_thresh': -50.0, 'tau_syn_E': 5.0, 'tau_syn_I': 5.0,
        'tau_refrac': 0.1, 'i_offset': 0, 'isyn_exc': 0.0, 'isyn_inh': 0.0,
        'tau_low_pass': 20.,
    }

    initialize_parameters = {'v_init': None}

    def __init__(
            self, n_neurons, spikes_per_second=_apv_defs['spikes_per_second'],
            ring_buffer_sigma=_apv_defs['ring_buffer_sigma'],
            incoming_spike_buffer_size=_apv_defs['incoming_spike_buffer_size'],
            constraints=_apv_defs['constraints'],
            label=_apv_defs['label'],
            tau_m=default_parameters['tau_m'],
            cm=default_parameters['cm'],
            v_rest=default_parameters['v_rest'],
            v_reset=default_parameters['v_reset'],
            v_thresh=default_parameters['v_thresh'],
            tau_syn_E=default_parameters['tau_syn_E'],
            tau_syn_I=default_parameters['tau_syn_I'],
            tau_refrac=default_parameters['tau_refrac'],
            i_offset=default_parameters['i_offset'],
            v_init=initialize_parameters['v_init'],
            isyn_exc=default_parameters['isyn_exc'],
            isyn_inh=default_parameters['isyn_inh'],
            tau_low_pass=default_parameters['tau_low_pass']):

        neuron_model = NeuronModelLeakyIntegrateAndFireDvDt(
            n_neurons, v_init, v_rest, tau_m, cm, i_offset,
            v_reset, tau_refrac, tau_low_pass)
        synapse_type = SynapseTypeExponential(
            n_neurons, tau_syn_E, tau_syn_I, isyn_exc, isyn_inh)
        input_type = InputTypeCurrent()
        threshold_type = ThresholdTypeStatic(n_neurons, v_thresh)

        AbstractPopulationVertex.__init__(
            self, n_neurons=n_neurons, binary="IF_curr_exp_dv.aplx", label=label,
            max_atoms_per_core=IFCurrExpDvDt._model_based_max_atoms_per_core,
            spikes_per_second=spikes_per_second,
            ring_buffer_sigma=ring_buffer_sigma,
            incoming_spike_buffer_size=incoming_spike_buffer_size,
            model_name="IF_curr_exp_dv", neuron_model=neuron_model,
            input_type=input_type, synapse_type=synapse_type,
            threshold_type=threshold_type, constraints=constraints)

    @staticmethod
    def set_model_max_atoms_per_core(new_value=DEFAULT_MAX_ATOMS_PER_CORE):
        IFCurrExpDvDt._model_based_max_atoms_per_core = new_value

    @staticmethod
    def get_max_atoms_per_core():
        return IFCurrExpDvDt._model_based_max_atoms_per_core

    @property
    def isyn_exc(self):
        return self.synapse_type.initial_value_exc

    @property
    def isyn_inh(self):
        return self.synapse_type.initial_value_inh

    @isyn_exc.setter
    def isyn_exc(self, new_value):
        self.synapse_type.initial_value_exc = new_value

    @isyn_inh.setter
    def isyn_inh(self, new_value):
        self.synapse_type.initial_value_inh = new_value