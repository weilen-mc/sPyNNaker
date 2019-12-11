# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy
from spinn_utilities.overrides import overrides
from data_specification.enums import DataType
from pacman.executor.injection_decorator import inject_items
from .abstract_additional_input import AbstractAdditionalInput

I_ALPHA = "i_alpha"
I_CA2 = "i_ca2"
TAU_CA2 = "tau_ca2"

UNITS = {
    I_ALPHA: "nA",
    I_CA2: "nA",
    TAU_CA2: "ms"
}


class AdditionalInputCa2Adaptive(AbstractAdditionalInput):
    __slots__ = [
        "__tau_ca2",
        "__i_ca2",
        "__i_alpha"]

    def __init__(self,  tau_ca2, i_ca2, i_alpha):
        super(AdditionalInputCa2Adaptive, self).__init__([
            DataType.S1615,   # e^(-ts / tau_ca2)
            DataType.S1615,   # i_ca_2
            DataType.S1615])  # i_alpha
        self.__tau_ca2 = tau_ca2
        self.__i_ca2 = i_ca2
        self.__i_alpha = i_alpha

    @overrides(AbstractAdditionalInput.get_n_cpu_cycles)
    def get_n_cpu_cycles(self, n_neurons):
        # A bit of a guess
        return 3 * n_neurons

    @overrides(AbstractAdditionalInput.add_parameters)
    def add_parameters(self, parameters):
        parameters[TAU_CA2] = self.__tau_ca2
        parameters[I_ALPHA] = self.__i_alpha

    @overrides(AbstractAdditionalInput.add_state_variables)
    def add_state_variables(self, state_variables):
        state_variables[I_CA2] = self.__i_ca2

    @overrides(AbstractAdditionalInput.get_units)
    def get_units(self, variable):
        return UNITS[variable]

    @overrides(AbstractAdditionalInput.has_variable)
    def has_variable(self, variable):
        return variable in UNITS

    @overrides(AbstractAdditionalInput.get_values)
    def get_values(
            self, parameters, state_variables, vertex_slice, timestamp_in_us):
        # pylint: disable=arguments-differ

        # Add the rest of the data
        return [parameters[TAU_CA2].apply_operation(
                    operation=lambda x:
                    numpy.exp(float(-timestamp_in_us) / (1000.0 * x))),
                state_variables[I_CA2], parameters[I_ALPHA]]

    @overrides(AbstractAdditionalInput.update_values)
    def update_values(self, values, parameters, state_variables):

        # Read the data
        (_exp_tau_ca2, i_ca2, _i_alpha) = values

        # Copy the changed data only
        state_variables[I_CA2] = i_ca2

    @property
    def tau_ca2(self):
        return self.__tau_ca2

    @tau_ca2.setter
    def tau_ca2(self, tau_ca2):
        self.__tau_ca2 = tau_ca2

    @property
    def i_ca2(self):
        return self.__i_ca2

    @i_ca2.setter
    def i_ca2(self, i_ca2):
        self.__i_ca2 = i_ca2

    @property
    def i_alpha(self):
        return self.__i_alpha

    @i_alpha.setter
    def i_alpha(self, i_alpha):
        self.__i_alpha = i_alpha
