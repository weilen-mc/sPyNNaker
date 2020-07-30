import numpy

from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD

from spynnaker.pyNN.models.neuron.synapse_dynamics import SynapseDynamicsStatic
from spynnaker.pyNN.models.neural_projections.connectors import (
    OneToOneConnector)

from .generator_data import GeneratorData


# Address to indicate that the synaptic region is unused for the generator
_SYN_REGION_UNUSED = 0xFFFFFFFF


class SynapticMatrix(object):
    """ A single synaptic matrix
    """

    __slots__ = [
        "__synapse_io",
        "__poptable",
        "__synapse_info",
        "__machine_edge",
        "__app_edge",
        "__n_synapse_types",
        "__max_row_info",
        "__routing_info",
        "__delay_routing_info",
        "__weight_scales",
        "__all_syn_block_sz",
        "__all_single_syn_sz",
        "__matrix_size",
        "__delay_matrix_size",
        "__single_matrix_size",
        "__index",
        "__syn_mat_offset",
        "__delay_syn_mat_offset",
        "__is_single",
        "__received_block",
        "__delay_received_block"
    ]

    def __init__(self, synapse_io, poptable, synapse_info, machine_edge,
                 app_edge, n_synapse_types, max_row_info, routing_info,
                 delay_routing_info, weight_scales, all_syn_block_sz,
                 all_single_syn_sz):
        self.__synapse_io = synapse_io
        self.__poptable = poptable
        self.__synapse_info = synapse_info
        self.__machine_edge = machine_edge
        self.__app_edge = app_edge
        self.__n_synapse_types = n_synapse_types
        self.__max_row_info = max_row_info
        self.__routing_info = routing_info
        self.__delay_routing_info = delay_routing_info
        self.__weight_scales = weight_scales
        self.__all_syn_block_sz = all_syn_block_sz
        self.__all_single_syn_sz = all_single_syn_sz

        # The matrix size can be calculated up-front; use for checking later
        self.__matrix_size = (
            self.__max_row_info.undelayed_max_bytes *
            self.__machine_edge.pre_vertex.vertex_slice.n_atoms)
        self.__delay_matrix_size = (
            self.__max_row_info.delayed_max_bytes *
            self.__machine_edge.pre_vertex.vertex_slice.n_atoms *
            self.__app_edge.n_delay_stages)
        self.__single_matrix_size = (
            self.__machine_edge.pre_vertex.vertex_slice.n_atoms *
            BYTES_PER_WORD)

        self.__index = None
        self.__syn_mat_offset = None
        self.__delay_syn_mat_offset = None
        self.__is_single = False
        self.__received_block = None
        self.__delay_received_block = None

    @property
    def is_delayed(self):
        """ Is there a delay matrix?

        :rtype: bool
        """
        return self.__app_edge.n_delay_stages > 0

    def is_direct(self, single_addr):
        """ Determine if the given connection can be done with a "direct"\
            synaptic matrix - this must have an exactly 1 entry per row

        :param int single_addr: The current offset of the direct matrix
        :return: A tuple of a boolean indicating if the matrix is direct and
            the next offset of the single matrix
        :rtype: (bool, int)
        """
        pre_vertex_slice = self.__machine_edge.pre_vertex.vertex_slice
        post_vertex_slice = self.__machine_edge.post_vertex.vertex_slice
        next_addr = single_addr + self.__single_matrix_size
        is_direct = (
            next_addr <= self.__all_single_syn_sz and
            not self.is_delayed and
            isinstance(self.__synapse_info.connector, OneToOneConnector) and
            isinstance(self.__synapse_info.synapse_dynamics,
                       SynapseDynamicsStatic) and
            (pre_vertex_slice.lo_atom == post_vertex_slice.lo_atom) and
            (pre_vertex_slice.hi_atom == post_vertex_slice.hi_atom) and
            not self.__synapse_info.prepop_is_view and
            not self.__synapse_info.postpop_is_view)
        return is_direct, next_addr

    def get_row_data(self):
        """ Generate the row data for a synaptic matrix from the description
        """

        (row_data, delayed_row_data, delayed_source_ids,
         delay_stages) = self.__synapse_io.get_synapses(
            self.__synapse_info, self.__app_edge.n_delay_stages,
            self.__n_synapse_types, self.__weight_scales,
            self.__machine_edge, self.__max_row_info)

        if self.__app_edge.delay_edge is not None:
            pre_vertex_slice = self.__machine_edge.pre_vertex.vertex_slice
            self.__app_edge.delay_edge.pre_vertex.add_delays(
                pre_vertex_slice, delayed_source_ids, delay_stages)
        elif delayed_source_ids.size != 0:
            raise Exception(
                "Found delayed source IDs but no delay "
                "edge for {}".format(self.__app_edge.label))

        return (row_data, delayed_row_data)

    def write_machine_matrix(
            self, spec, block_addr, single_synapses, single_addr, row_data):
        """ Write a matrix for an incoming machine vertex
        """
        if self.__max_row_info.undelayed_max_n_synapses == 0:
            # If there is routing information, write an invalid entry
            if self.__routing_info is not None:
                index = self.__poptable.add_invalid_entry(
                    self.__routing_info.first_key_and_mask)
                self.__update_synapse_index(index)
            return block_addr, single_addr

        size = len(row_data) * BYTES_PER_WORD
        if size != self.__matrix_size:
            raise Exception("Data is incorrect size: {} instead of {}".format(
                size, self.__matrix_size))

        is_direct, _ = self.is_direct(single_addr)
        if is_direct:
            single_addr = self.__write_single_machine_matrix(
                single_synapses, single_addr, row_data)
            return block_addr, single_addr

        block_addr = self.__poptable.write_padding(spec, block_addr)
        index = self.__poptable.update_master_population_table(
            block_addr, self.__max_row_info.undelayed_max_words,
            self.__routing_info.first_key_and_mask)
        self.__update_synapse_index(index)
        spec.write_array(row_data)
        self.__syn_mat_offset = block_addr
        block_addr = self.__next_addr(block_addr, self.__matrix_size)
        return block_addr, single_addr

    def write_delayed_machine_matrix(self, spec, block_addr, row_data):
        """ Write a matrix for an incoming machine vertex
        """
        if self.__max_row_info.delayed_max_n_synapses == 0:
            # If there is routing information, write an invalid entry
            if self.__delay_routing_info is not None:
                index = self.__poptable.add_invalid_entry(
                    self.__delay_routing_info.first_key_and_mask)
                self.__update_synapse_index(index)
            return block_addr

        size = len(row_data) * BYTES_PER_WORD
        if size != self.__delay_matrix_size:
            raise Exception("Data is incorrect size: {} instead of {}".format(
                size, self.__delay_matrix_size))

        block_addr = self.__poptable.write_padding(spec, block_addr)
        index = self.__poptable.update_master_population_table(
            block_addr, self.__max_row_info.delayed_max_words,
            self.__delay_routing_info.first_key_and_mask)
        self.__update_synapse_index(index)
        spec.write_array(row_data)
        self.__delay_syn_mat_offset = block_addr
        block_addr = self.__next_addr(block_addr, self.__delay_matrix_size)
        return block_addr

    def __write_single_machine_matrix(
            self, single_synapses, single_addr, row_data):
        """ Write a direct (single synapse) matrix for an incoming machine\
            vertex
        """
        single_rows = row_data.reshape(-1, 4)[:, 3]
        data_size = len(single_rows) * BYTES_PER_WORD
        if data_size != self.__single_matrix_size:
            raise Exception("Row data incorrect size: {} instead of {}".format(
                data_size, self.__single_matrix_size))
        index = self.__poptable.update_master_population_table(
            single_addr, self.__max_row_info.undelayed_max_words,
            self.__routing_info.first_key_and_mask, is_single=True)
        self.__update_synapse_index(index)
        single_synapses.append(single_rows)
        self.__syn_mat_offset = single_addr
        self.__is_single = True
        single_addr = single_addr + self.__single_matrix_size
        return single_addr

    def write_on_chip_delay_data(self):
        """ Write data for delayed on-chip generation
        """
        # If delay edge exists, tell this about the data too, so it can
        # generate its own data
        if (self.__max_row_info.delayed_max_n_synapses > 0 and
                self.__app_edge.delay_edge is not None):
            self.__app_edge.delay_edge.pre_vertex.add_generator_data(
                self.__max_row_info.undelayed_max_n_synapses,
                self.__max_row_info.delayed_max_n_synapses,
                self.__app_edge.pre_vertex.vertex_slices,
                self.__machine_edge.pre_vertex.index,
                self.__app_edge.post_vertex.vertex_slices,
                self.__machine_edge.post_vertex.index,
                self.__machine_edge.pre_vertex.vertex_slice,
                self.__machine_edge.post_vertex.vertex_slice,
                self.__synapse_info, self.__app_edge.n_delay_stages + 1)
        elif self.__max_row_info.delayed_max_n_synapses != 0:
            raise Exception(
                "Found delayed items but no delay machine edge for {}".format(
                    self.__app_edge.label))

    def next_app_on_chip_address(self, app_block_addr, max_app_addr):
        if self.__max_row_info.undelayed_max_n_synapses == 0:
            return app_block_addr, _SYN_REGION_UNUSED

        addr = app_block_addr
        app_block_addr = self.__next_addr(
            app_block_addr, self.__matrix_size, max_app_addr)
        return app_block_addr, addr

    def next_app_delay_on_chip_address(self, app_block_addr, max_app_addr):
        if self.__max_row_info.delayed_max_n_synapses == 0:
            return app_block_addr, _SYN_REGION_UNUSED

        addr = app_block_addr
        app_block_addr = self.__next_addr(
            app_block_addr, self.__delay_matrix_size, max_app_addr)
        return app_block_addr, addr

    def next_on_chip_address(self, block_addr):
        # If there isn't any synapses, add an invalid entry
        if self.__max_row_info.undelayed_max_n_synapses == 0:
            if self.__routing_info is not None:
                index = self.__poptable.add_invalid_entry(
                    self.__routing_info.first_key_and_mask)
                self.__update_synapse_index(index)
            return block_addr, _SYN_REGION_UNUSED

        # Otherwise add a master population table entry for the incoming
        # machine vertex
        index = self.__poptable.update_master_population_table(
            block_addr, self.__max_row_info.undelayed_max_words,
            self.__routing_info.first_key_and_mask)
        self.__update_synapse_index(index)
        self.__syn_mat_offset = block_addr
        block_addr = self.__next_addr(block_addr, self.__matrix_size)
        return block_addr, self.__syn_mat_offset

    def next_delay_on_chip_address(self, block_addr):
        # If there isn't any synapses, add an invalid entry
        if self.__max_row_info.delayed_max_n_synapses == 0:
            if self.__delay_routing_info is not None:
                index = self.__poptable.add_invalid_entry(
                    self.__delay_routing_info.first_key_and_mask)
                self.__update_synapse_index(index)
            return block_addr, _SYN_REGION_UNUSED

        # Otherwise add a master population table entry for the incoming
        # machine vertex
        index = self.__poptable.update_master_population_table(
            block_addr, self.__max_row_info.delayed_max_words,
            self.__delay_routing_info.first_key_and_mask)
        self.__update_synapse_index(index)
        self.__delay_syn_mat_offset = block_addr
        block_addr = self.__next_addr(block_addr, self.__delay_matrix_size)
        return block_addr, self.__delay_syn_mat_offset

    def get_generator_data(self, syn_mat_offset, d_mat_offset):
        return GeneratorData(
            syn_mat_offset, d_mat_offset,
            self.__max_row_info.undelayed_max_words,
            self.__max_row_info.delayed_max_words,
            self.__max_row_info.undelayed_max_n_synapses,
            self.__max_row_info.delayed_max_n_synapses,
            self.__app_edge.pre_vertex.vertex_slices,
            self.__machine_edge.pre_vertex.index,
            self.__app_edge.post_vertex.vertex_slices,
            self.__machine_edge.post_vertex.index,
            self.__machine_edge.pre_vertex.vertex_slice,
            self.__machine_edge.post_vertex.vertex_slice,
            self.__synapse_info, self.__app_edge.n_delay_stages + 1,
            globals_variables.get_simulator().machine_time_step)

    def __next_addr(self, block_addr, size, max_addr=None):
        """ Get a block address and check it hasn't overflowed the allocation
        """
        next_addr = block_addr + size
        if max_addr is None:
            max_addr = self.__all_syn_block_sz
        if next_addr > max_addr:
            raise Exception(
                "Too much synaptic memory has been used: {} of {}".format(
                    next_addr, max_addr))
        return next_addr

    def __update_synapse_index(self, index):
        """ Update the index of a synapse, checking it matches against indices\
            for other synapse_info for the same edge
        """
        if self.__index is None:
            self.__index = index
        elif self.__index != index:
            # This should never happen as things should be aligned over all
            # machine vertices, but check just in case!
            raise Exception(
                "Index of " + self.__synapse_info + " has changed!")

    def read_connections(
            self, transceiver, placement, synapses_address, single_address):
        pre_slice = self.__machine_edge.pre_vertex.vertex_slice
        post_slice = self.__machine_edge.post_vertex.vertex_slice
        machine_time_step = globals_variables.get_simulator().machine_time_step
        connections = list()

        if self.__syn_mat_offset is not None:
            if self.is_single:
                block = self.__get_single_block(
                    transceiver, placement, single_address)
            else:
                block = self.__get_block(
                    transceiver, placement, synapses_address)
            connections.append(self.__synapse_io.read_some_synapses(
                self.__synapse_info, pre_slice, post_slice,
                self.__max_row_info.undelayed_max_words,
                self.__n_synapse_types, self.__weight_scales[placement], block,
                machine_time_step, delayed=False))

        if self.__delay_syn_mat_offset is not None:
            block = self.__get_delayed_block(
                transceiver, placement, synapses_address)
            connections.append(self.__synapse_io.read_some_synapses(
                self.__synapse_info, pre_slice, post_slice,
                self.__max_row_info.delayed_max_words, self.__n_synapse_types,
                self.__weight_scales[placement], block,
                machine_time_step, delayed=True))

        return connections

    def clear_connection_cache(self):
        self.__received_block = None
        self.__delay_received_block = None

    def __get_block(self, transceiver, placement, synapses_address):
        if self.__received_block is not None:
            return self.__received_block
        address = self.__syn_mat_offset + synapses_address
        block = transceiver.read_memory(
            placement.x, placement.y, address, self.__matrix_size)
        self.__received_block = block
        return block

    def __get_delayed_block(self, transceiver, placement, synapses_address):
        if self.__delay_received_block is not None:
            return self.__delay_received_block
        address = self.__delay_syn_mat_offset + synapses_address
        block = transceiver.read_memory(
            placement.x, placement.y, address, self.__delay_matrix_size)
        self.__received_block = block
        return block

    def __get_single_block(self, transceiver, placement, single_address):
        if self.__received_block is not None:
            return self.__received_block
        address = self.__syn_mat_offset + single_address
        block = transceiver.read_memory(
            placement.x, placement.y, address, self.__single_matrix_size)
        numpy_data = numpy.asarray(block, dtype="uint8").view("uint32")
        n_rows = len(numpy_data)
        numpy_block = numpy.zeros((n_rows, BYTES_PER_WORD), dtype="uint32")
        numpy_block[:, 3] = numpy_data
        numpy_block[:, 1] = 1
        self.__received_block = numpy_block
        return numpy_block.tobytes()