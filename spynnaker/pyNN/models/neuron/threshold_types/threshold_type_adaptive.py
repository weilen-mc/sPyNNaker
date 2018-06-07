from pacman.model.decorators import overrides

from pacman.executor.injection_decorator import inject_items
from spynnaker.pyNN.models.abstract_models import AbstractContainsUnits
from spynnaker.pyNN.models.neural_properties import NeuronParameter
from spynnaker.pyNN.utilities.ranged.spynakker_ranged_dict import \
    SpynakkerRangeDictionary
from .abstract_threshold_type import AbstractThresholdType

from data_specification.enums import DataType
import numpy
from enum import Enum

V_THRESH = "v_thresh"
V_THRESH_RESTING = "v_thresh_resting"
V_THRESH_TAU = "v_thresh_tau"
V_THRESH_ADAPT = "v_thresh_adaptation"

class _ADAPTIVE_TYPES(Enum):
    V_THRESH = (1, DataType.S1615) # instantaneous threshold level
    V_THRESH_RESTING = (2, DataType.S1615) # baseline threshold
    EXP_THRESH_TAU = (3, DataType.S1615) # time constant for
                                         # threshold to decay back to baseline
    V_THRESH_ADAPT = (4, DataType.S1615) # Adaptation on spiking

    def __new__(cls, value, data_type):
        obj = object.__new__(cls)
        obj._value_ = value
        obj._data_type = data_type
        return obj

    @property
    def data_type(self):
        return self._data_type


class ThresholdTypeAdaptive(AbstractThresholdType, AbstractContainsUnits):

    """ A threshold which increases when the neuron spikes, and decays exponentially
        back to baseline with time
    """

    def __init__(self, n_neurons, v_thresh,
                 v_thresh_resting, v_thresh_tau, v_thresh_adaptation):
        AbstractThresholdType.__init__(self)
        AbstractContainsUnits.__init__(self)

        self._units = {V_THRESH: "mV",
                       V_THRESH_RESTING: "mV",
                       V_THRESH_TAU: "ms",
                       V_THRESH_ADAPT: "mV"}

        self._n_neurons = n_neurons
        self._data = SpynakkerRangeDictionary(size=n_neurons)
        self._data[V_THRESH] = v_thresh
        self._data[V_THRESH_RESTING] = v_thresh_resting
        self._data[V_THRESH_TAU] = v_thresh_tau
        self._data[V_THRESH_ADAPT] = v_thresh_adaptation


    @property
    def v_thresh(self):
        return self._data[V_THRESH]

    @v_thresh.setter
    def v_thresh(self, v_thresh):
        self._data.set_value(key=V_THRESH, value=v_thresh)

    @property
    def v_thresh_resting(self):
        return self._data[V_THRESH_RESTING]

    @v_thresh_resting.setter
    def v_thresh_resting(self, v_thresh_resting):
        self._data.set_value(key=V_THRESH_RESTING, value=v_thresh_resting)

    @property
    def v_thresh_tau(self):
        return self._data[V_THRESH_TAU]

    @v_thresh_tau.setter
    def v_thresh_tau(self, v_thresh_tau):
        self._data.set_value(key=V_THRESH_TAU, value=v_thresh_tau)

    @property
    def v_thresh_adaptation(self):
        return self._data[V_THRESH_ADAPT]

    @v_thresh_adaptation.setter
    def v_thresh_adaptation(self, v_thresh_adaptation):
        self._data.set_value(key=V_THRESH_ADAPT, value=v_thresh_adaptation)

    @overrides(AbstractThresholdType.get_n_threshold_parameters)
    def get_n_threshold_parameters(self):
        return 4

    @inject_items({"machine_time_step": "MachineTimeStep"})
    def _exp_thresh_tau(self, machine_time_step):
        return self._data[V_THRESH_TAU].apply_operation(
            operation=lambda x: numpy.exp(
                float(-machine_time_step) / (1000.0 * x)))


    @overrides(AbstractThresholdType.get_threshold_parameters)
    def get_threshold_parameters(self):
        return [
            NeuronParameter(self._data[V_THRESH],
                            _ADAPTIVE_TYPES.V_THRESH.data_type),

            NeuronParameter(self._data[V_THRESH_RESTING],
                            _ADAPTIVE_TYPES.V_THRESH_RESTING.data_type),

            NeuronParameter(self._exp_thresh_tau(),
                            _ADAPTIVE_TYPES.EXP_THRESH_TAU.data_type),

            NeuronParameter(self._data[V_THRESH_ADAPT],
                            _ADAPTIVE_TYPES.V_THRESH_ADAPT.data_type),
        ]

    @overrides(AbstractThresholdType.get_threshold_parameter_types)
    def get_threshold_parameter_types(self):
        return [item.data_type for item in _ADAPTIVE_TYPES]

    def get_n_cpu_cycles_per_neuron(self):

        # Just a comparison, but 2 just in case!
        return 10

    @overrides(AbstractContainsUnits.get_units)
    def get_units(self, variable):
        return self._units[variable]