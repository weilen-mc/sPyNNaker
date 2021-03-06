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

import logging
import numpy
from six import string_types, iteritems
from spinn_utilities.logger_utils import warn_once
from spinn_utilities.log import FormatAdapter
from pacman.model.constraints import AbstractConstraint
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.constraints.partitioner_constraints import (
    MaxVertexAtomsConstraint)
from pacman.model.graphs.application.application_vertex import (
    ApplicationVertex)
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.abstract_models import AbstractChangableAfterRun
from spynnaker.pyNN.models.abstract_models import (
    AbstractReadParametersBeforeSet, AbstractContainsUnits,
    AbstractPopulationInitializable, AbstractPopulationSettable)
from .abstract_pynn_model import AbstractPyNNModel

logger = FormatAdapter(logging.getLogger(__file__))


def _we_dont_do_this_now(*args):  # pylint: disable=unused-argument
    # pragma: no cover
    raise NotImplementedError("sPyNNaker8 does not currently do this")


class PyNNPopulationCommon(object):
    """ Base class for PyNN populations.
    """
    __slots__ = [
        "_all_ids",
        "__change_requires_mapping",
        "__delay_vertex",
        "__first_id",
        "__has_read_neuron_parameters_this_run",
        "__last_id",
        "_positions",
        "__record_gsyn_file",
        "__record_spike_file",
        "__record_v_file",
        "_size",
        "__spinnaker_control",
        "__structure",
        "__vertex",
        "_vertex_changeable_after_run",
        "_vertex_contains_units",
        "_vertex_population_initializable",
        "_vertex_population_settable",
        "_vertex_read_parameters_before_set"]

    def __init__(
            self, spinnaker_control, size, label, constraints, model,
            structure, initial_values, additional_parameters=None):
        """
        :param spinnaker_control: The simulator engine core.
        :type spinnaker_control:
            ~spinn_front_end_common.interface.abstract_spinnaker_base.AbstractSpinnakerBase
        :param size: The size of the population; external devices may use None
        :type size: int or float or None
        :param label: The label for the population, or None for a default
        :type label: str or None
        :param list(~pacman.model.constraints.AbstractConstraint) constraints:
            How do we constrain where to put things on SpiNNaker
        :param model: What neuron model is being run by this population
        :type model:
            AbstractPyNNModel or
            ~pacman.model.graphs.application.ApplicationVertex
        :param structure: How the neurons are arranged in space
        :type structure: ~pyNN.space.BaseStructure or None
        :param initial_values: Initialisation for model variables.
        :type initial_values: dict(str, Any) or None
        :param additional_parameters:
            Any extra parameters to pass to the model's vertex creation \
            function.
        :type additional_parameters: dict(str, Any) or None
        """
        # pylint: disable=too-many-arguments
        size = self.__roundsize(size, label)

        # Use a provided model to create a vertex
        if isinstance(model, AbstractPyNNModel):
            if size is not None and size <= 0:
                raise ConfigurationException(
                    "A population cannot have a negative or zero size.")
            population_parameters = dict(model.default_population_parameters)
            if additional_parameters is not None:
                population_parameters.update(additional_parameters)
            self.__vertex = model.create_vertex(
                size, label, constraints, **population_parameters)

        # Use a provided application vertex directly
        elif isinstance(model, ApplicationVertex):
            if additional_parameters is not None:
                raise ConfigurationException(
                    "Cannot accept additional parameters {} when the cell is"
                    " a vertex".format(additional_parameters))
            self.__vertex = model
            if size is None:
                size = self.__vertex.n_atoms
            elif size != self.__vertex.n_atoms:
                raise ConfigurationException(
                    "Vertex size does not match Population size")
            if label is not None:
                self.__vertex.set_label(label)
            if constraints is not None:
                self.__vertex.add_constraints(constraints)

        # Fail on anything else
        else:
            raise ConfigurationException(
                "Model must be either an AbstractPyNNModel or an"
                " ApplicationVertex")

        # Introspect properties of the vertex
        self._vertex_population_settable = \
            isinstance(self.__vertex, AbstractPopulationSettable)
        self._vertex_population_initializable = \
            isinstance(self.__vertex, AbstractPopulationInitializable)
        self._vertex_changeable_after_run = \
            isinstance(self.__vertex, AbstractChangableAfterRun)
        self._vertex_read_parameters_before_set = \
            isinstance(self.__vertex, AbstractReadParametersBeforeSet)
        self._vertex_contains_units = \
            isinstance(self.__vertex, AbstractContainsUnits)

        self.__spinnaker_control = spinnaker_control
        self.__delay_vertex = None

        # Internal structure now supported 23 November 2014 ADR
        # structure should be a valid Space.py structure type.
        # generation of positions is deferred until needed.
        self.__structure = structure
        self._positions = None

        # add objects to the SpiNNaker control class
        self.__spinnaker_control.add_population(self)
        self.__spinnaker_control.add_application_vertex(
            self.__vertex)

        # initialise common stuff
        self._size = size
        self.__record_spike_file = None
        self.__record_v_file = None
        self.__record_gsyn_file = None

        # parameter
        self.__change_requires_mapping = True
        self.__has_read_neuron_parameters_this_run = False

        # things for pynn demands
        self._all_ids = numpy.arange(
            globals_variables.get_simulator().id_counter,
            globals_variables.get_simulator().id_counter + size)
        self.__first_id = self._all_ids[0]
        self.__last_id = self._all_ids[-1]

        # update the simulators id_counter for giving a unique ID for every
        # atom
        globals_variables.get_simulator().id_counter += size

        # set up initial values if given
        if initial_values is not None:
            for variable, value in iteritems(initial_values):
                self._initialize(variable, value)

    @property
    def first_id(self):
        """ The ID of the first member of the population.

        :rtype: int
        """
        return self.__first_id

    @property
    def last_id(self):
        """ The ID of the last member of the population.

        :rtype: int
        """
        return self.__last_id

    @property
    def _structure(self):
        """
        :rtype: ~pyNN.space.BaseStructure or None
        """
        return self.__structure

    @property
    def _vertex(self):
        """
        :rtype: ~pacman.model.graphs.application.ApplicationVertex
        """
        return self.__vertex

    @property
    def requires_mapping(self):
        """ Whether this population requires mapping.

        :rtype: bool
        """
        return self.__change_requires_mapping

    @requires_mapping.setter
    def requires_mapping(self, new_value):
        self.__change_requires_mapping = new_value

    def mark_no_changes(self):
        """ Mark this population as not having changes to be mapped.
        """
        self.__change_requires_mapping = False
        self.__has_read_neuron_parameters_this_run = False

    def __add__(self, other):
        """ Merges populations
        """
        # TODO: Make this add the neurons from another population to this one
        _we_dont_do_this_now(other)

    @property
    def conductance_based(self):
        """ True if the population uses conductance inputs

        :rtype: bool
        """
        if hasattr(self.__vertex, "conductance_based"):
            return self.__vertex.conductance_based
        return False

    def get(self, parameter_names, gather=True, simplify=True):
        """ Get the values of a parameter for every local cell in the\
            population.

        :param parameter_names: Name of parameter. This is either a single\
            string or a list of strings
        :type parameter_names: str or iterable(str)
        :param bool gather: pointless on sPyNNaker
        :param bool simplify: ignored
        :return: A single list of values (or possibly a single value) if\
            paramter_names is a string, or a dict of these if parameter names\
            is a list.
        :rtype: str or list(str) or dict(str,str) or dict(str,list(str))
        """
        if not gather:
            warn_once(
                logger, "sPyNNaker only supports gather=True. We will run "
                "as if gather was set to True.")
        if simplify is not True:
            warn_once(
                logger, "The simplify value is ignored if not set to true")
        if not self._vertex_population_settable:
            raise KeyError("Population does not support setting")
        if isinstance(parameter_names, string_types):
            return self.__vertex.get_value(parameter_names)
        results = dict()
        for parameter_name in parameter_names:
            results[parameter_name] = self.__vertex.get_value(parameter_name)
        return results

    # NON-PYNN API CALL
    def get_by_selector(self, selector, parameter_names):
        """ Get the values of a parameter for the selected cell in the\
            population.

        :param selector: a description of the subrange to accept. \
            Or None for all. See: \
            :py:meth:`~spinn_utilities.ranged.AbstractSized.selector_to_ids`
        :type selector: slice or int or iterable(bool) or iterable(int)
        :param parameter_names: Name of parameter. This is either a\
            single string or a list of strings
        :type parameter_names: str or iterable(str)
        :return: A single list of values (or possibly a single value) if\
            paramter_names is a string or a dict of these if parameter names\
            is a list.
        :rtype: str or list(str) or dict(str,str) or dict(str,list(str))
        """
        if not self._vertex_population_settable:
            raise KeyError("Population does not support setting")
        if isinstance(parameter_names, string_types):
            return self.__vertex.get_value_by_selector(
                selector, parameter_names)
        results = dict()
        for parameter_name in parameter_names:
            results[parameter_name] = self.__vertex.get_value_by_selector(
                selector, parameter_name)
        return results

    def id_to_index(self, id):  # @ReservedAssignment
        """ Given the ID(s) of cell(s) in the Population, return its (their)\
            index (order in the Population).

        Defined by
        http://neuralensemble.org/docs/PyNN/reference/populations.html

        :param id:
        :type id: int or iterable(int)
        :rtype: int or iterable(int)
        """
        # pylint: disable=redefined-builtin
        if not numpy.iterable(id):
            if not self.__first_id <= id <= self.__last_id:
                raise ValueError(
                    "id should be in the range [{},{}], actually {}".format(
                        self.__first_id, self.__last_id, id))
            return int(id - self.__first_id)  # assume IDs are consecutive
        return id - self.__first_id

    def index_to_id(self, index):
        """ Given the index (order in the Population) of cell(s) in the\
            Population, return their ID(s)

        :param index:
        :type index: int or iterable(int)
        :rtype: int or iterable(int)
        """
        if not numpy.iterable(index):
            if index > self.__last_id - self.__first_id:
                raise ValueError(
                    "indexes should be in the range [{},{}], actually {}"
                    "".format(0, self.__last_id - self.__first_id, index))
            return int(index + self.__first_id)
        # this assumes IDs are consecutive
        return index + self.__first_id

    def id_to_local_index(self, cell_id):
        """ Given the ID(s) of cell(s) in the Population, return its (their)\
            index (order in the Population), counting only cells on the local\
            MPI node.

        Defined by
        http://neuralensemble.org/docs/PyNN/reference/populations.html

        :param cell_id:
        :type cell_id: int or iterable(int)
        :rtype: int or iterable(int)
        """
        # TODO: Need __getitem__
        _we_dont_do_this_now(cell_id)

    def _initialize(self, variable, value):
        """ Set the initial value of one of the state variables of the neurons\
            in this population.

        :param str variable:
        :param value:
        :type value: float or int or list(float) or list(int)
        """
        if not self._vertex_population_initializable:
            raise KeyError(
                "Population does not support the initialisation of {}".format(
                    variable))
        if globals_variables.get_not_running_simulator().has_ran \
                and not self._vertex_changeable_after_run:
            raise Exception("Population does not support changes after run")
        self._read_parameters_before_set()
        self.__vertex.initialize(variable, value)

    def inject(self, current_source):
        """ Connect a current source to all cells in the Population.

        Defined by
        http://neuralensemble.org/docs/PyNN/reference/populations.html
        """
        # TODO:
        _we_dont_do_this_now(current_source)

    def __len__(self):
        """ Get the total number of cells in the population.
        """
        return self._size

    @property
    def label(self):
        """ The label of the population

        :rtype: str
        """
        return self._vertex.label

    @label.setter
    def label(self, label):
        raise NotImplementedError(
            "As label is used as an ID it can not be changed")

    @property
    def local_size(self):
        """ The number of local cells

        Defined by
        http://neuralensemble.org/docs/PyNN/reference/populations.html
        """
        # Doesn't make much sense on SpiNNaker
        return self._size

    def _set_check(self, parameter, value):
        """ Checks for various set methods.
        """
        if not self._vertex_population_settable:
            raise KeyError("Population does not have property {}".format(
                parameter))

        if globals_variables.get_not_running_simulator().has_ran \
                and not self._vertex_changeable_after_run:
            raise Exception(
                " run has been called")

        if isinstance(parameter, string_types):
            if value is None:
                raise Exception("A value (not None) must be specified")
        elif type(parameter) is not dict:
            raise Exception(
                "Parameter must either be the name of a single parameter to"
                " set, or a dict of parameter: value items to set")

        self._read_parameters_before_set()

    def set(self, parameter, value=None):
        """ Set one or more parameters for every cell in the population.

        param can be a dict, in which case value should not be supplied, or a\
        string giving the parameter name, in which case value is the parameter\
        value. value can be a numeric value, or list of such\
        (e.g. for setting spike times)::

            p.set("tau_m", 20.0).
            p.set({'tau_m':20, 'v_rest':-65})

        :param parameter: the parameter to set
        :type parameter: str or dict(str, Any)
        :param Any value: the value of the parameter to set.
        """
        self._set_check(parameter, value)

        # set new parameters
        if isinstance(parameter, string_types):
            if value is None:
                raise Exception("A value (not None) must be specified")
            self.__vertex.set_value(parameter, value)
            return
        for (key, value) in parameter.iteritems():
            self.__vertex.set_value(key, value)

    # NON-PYNN API CALL
    def set_by_selector(self, selector, parameter, value=None):
        """ Set one or more parameters for selected cell in the population.

        param can be a dict, in which case value should not be supplied, or a\
        string giving the parameter name, in which case value is the parameter\
        value. value can be a numeric value, or list of such
        (e.g. for setting spike times)::

            p.set("tau_m", 20.0).
            p.set({'tau_m':20, 'v_rest':-65})

        :param selector:
            See :py:meth:`RangedList.set_value_by_selector` as this is just a
            pass through method
        :param parameter: the parameter to set
        :type parameter: str or dict(str, float or int)
        :param value: the value of the parameter to set.
        :type value: float or int
        """
        self._set_check(parameter, value)

        # set new parameters
        if type(parameter) is str:
            self.__vertex.set_value_by_selector(selector, parameter, value)
        else:
            for (key, value) in parameter.iteritems():
                self.__vertex.set_value_by_selector(selector, key, value)

    def _read_parameters_before_set(self):
        """ Reads parameters from the machine before "set" completes

        :return: None
        """

        # If the tools have run before, and not reset, and the read
        # hasn't already been done, read back the data
        if globals_variables.get_simulator().has_ran \
                and self._vertex_read_parameters_before_set \
                and not self.__has_read_neuron_parameters_this_run \
                and not globals_variables.get_simulator().use_virtual_board:
            # go through each machine vertex and read the neuron parameters
            # it contains
            for machine_vertex in self.__vertex.machine_vertices:
                # tell the core to rewrite neuron params back to the
                # SDRAM space.
                placement = globals_variables.get_simulator().placements.\
                    get_placement_of_vertex(machine_vertex)

                self.__vertex.read_parameters_from_machine(
                    globals_variables.get_simulator().transceiver, placement,
                    machine_vertex.vertex_slice)

            self.__has_read_neuron_parameters_this_run = True

    def get_spike_counts(self, spikes, gather=True):
        """ Return the number of spikes for each neuron.

        Defined by
        http://neuralensemble.org/docs/PyNN/reference/populations.html

        :param ~numpy.ndarray spikes:
        :param gather: pointless on sPyNNaker
        :rtype: dict(int,int)
        """
        if not gather:
            warn_once(
                logger, "sPyNNaker only supports gather=True. We will run "
                "as if gather was set to True.")
        n_spikes = {}
        counts = numpy.bincount(spikes[:, 0].astype(dtype=numpy.int32),
                                minlength=self.__vertex.n_atoms)
        for i in range(self.__vertex.n_atoms):
            n_spikes[i] = counts[i]
        return n_spikes

    @property
    def positions(self):
        """ Return the position array for structured populations.
        """
        if self._positions is None:
            if self.__structure is None:
                raise ValueError("attempted to retrieve positions "
                                 "for an unstructured population")
            self._positions = self.__structure.generate_positions(
                self.__vertex.n_atoms)
        return self._positions

    @property
    def structure(self):
        """ Return the structure for the population.

        :rtype: ~pyNN.space.BaseStructure or None
        """
        return self.__structure

    # NON-PYNN API CALL
    def set_constraint(self, constraint):
        """ Apply a constraint to a population that restricts the processor\
            onto which its atoms will be placed.

        :param ~pacman.model.constraints.AbstractConstraint constraint:
        """
        globals_variables.get_simulator().verify_not_running()
        if not isinstance(constraint, AbstractConstraint):
            raise ConfigurationException(
                "the constraint entered is not a recognised constraint")

        self.__vertex.add_constraint(constraint)
        # state that something has changed in the population,
        self.__change_requires_mapping = True

    # NON-PYNN API CALL
    def add_placement_constraint(self, x, y, p=None):
        """ Add a placement constraint

        :param int x: The x-coordinate of the placement constraint
        :param int y: The y-coordinate of the placement constraint
        :param int p: The processor ID of the placement constraint (optional)
        """
        globals_variables.get_simulator().verify_not_running()
        self.__vertex.add_constraint(ChipAndCoreConstraint(x, y, p))

        # state that something has changed in the population,
        self.__change_requires_mapping = True

    # NON-PYNN API CALL
    def set_mapping_constraint(self, constraint_dict):
        """ Add a placement constraint - for backwards compatibility

        :param dict(str,int) constraint_dict:
            A dictionary containing "x", "y" and optionally "p" as keys, and
            ints as values
        """
        globals_variables.get_simulator().verify_not_running()
        self.add_placement_constraint(**constraint_dict)

        # state that something has changed in the population,
        self.__change_requires_mapping = True

    # NON-PYNN API CALL
    def set_max_atoms_per_core(self, max_atoms_per_core):
        """ Supports the setting of this population's max atoms per core

        :param int max_atoms_per_core:
            the new value for the max atoms per core.
        """
        globals_variables.get_simulator().verify_not_running()
        self.__vertex.add_constraint(
            MaxVertexAtomsConstraint(max_atoms_per_core))
        # state that something has changed in the population
        self.__change_requires_mapping = True

    @property
    def size(self):
        """ The number of neurons in the population

        :rtype: int
        """
        return self.__vertex.n_atoms

    @property
    def _get_vertex(self):
        """
        :rtype: ~pacman.model.graphs.application.ApplicationVertex
        """
        # Overridden by PopulationView
        return self.__vertex

    @property
    def _internal_delay_vertex(self):
        """
        """
        return self.__delay_vertex

    @_internal_delay_vertex.setter
    def _internal_delay_vertex(self, delay_vertex):
        self.__delay_vertex = delay_vertex
        self.__change_requires_mapping = True

    def _get_variable_unit(self, parameter_name):
        """ Helper method for getting units from a parameter used by the vertex

        :param str parameter_name: the parameter name to find the units for
        :return: the units in string form
        :rtype: str
        """
        if self._vertex_contains_units:
            return self.__vertex.get_units(parameter_name)
        raise ConfigurationException(
            "This population does not support describing its units")

    @staticmethod
    def __roundsize(size, label):
        # External device population can have a size of None so accept for now
        if size is None or isinstance(size, int):
            return size
        # Allow a float which has a near int value
        temp = int(round(size))
        if abs(temp - size) < 0.001:
            logger.warning("Size of the population rounded "
                           "from {} to {}. Please use int values for size",
                           label, size, temp)
            return temp
        raise ConfigurationException(
            "Size of a population with label {} must be an int,"
            " received {}".format(label, size))
