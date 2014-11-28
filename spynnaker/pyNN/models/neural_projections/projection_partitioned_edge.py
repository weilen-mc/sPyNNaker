from pacman.model.partitioned_graph.partitioned_edge import PartitionedEdge
from spynnaker.pyNN.models.abstract_models.abstract_filterable_edge import \
    AbstractFilterableEdge


class ProjectionPartitionedEdge(PartitionedEdge, AbstractFilterableEdge):
    def __init__(self, presubvertex, postsubvertex):
        PartitionedEdge.__init__(self, presubvertex, postsubvertex)
        AbstractFilterableEdge.__init__(self)
        self._synapse_sublist = None
        self._weight_scales = None

    @property
    def weight_scales(self):
        return self._weight_scales

    # **YUCK** setters don't work properly with inheritance
    def weight_scales_setter(self, value):
        self._weight_scales = value

    def get_synapse_sublist(self, graph_mapper):
        """
        Gets the synapse list for this subedge
        """
        pre_vertex_slice = \
            graph_mapper.get_subvertex_slice(self._pre_subvertex)
        post_vertex_slice = \
            graph_mapper.get_subvertex_slice(self._post_subvertex)
        if self._synapse_sublist is None:
            associated_edge = \
                graph_mapper.get_partitionable_edge_from_partitioned_edge(self)
            self._synapse_sublist = \
                associated_edge.synapse_list.create_atom_sublist(
                    pre_vertex_slice, post_vertex_slice)
        return self._synapse_sublist
    
    def free_sublist(self):
        """
        Indicates that the list will not be needed again
        """
        self._synapse_sublist = None

    def filter_sub_edge(self, graph_mapper, common_report_folder):
        """determines if theres an actual connection in this subedge in temrs of
        synaptic data

        """
        if self._synapse_sublist is None:
            self.get_synapse_sublist(graph_mapper)
            #reports.generate_synaptic_matrix_report(common_report_folder, self)

        pre_vertex_slice = graph_mapper.get_subvertex_slice(self._pre_subvertex)
        post_vertex_slice = \
            graph_mapper.get_subvertex_slice(self._post_subvertex)

        return not self._synapse_sublist.is_connected(pre_vertex_slice,
                                                      post_vertex_slice)

    @property
    def synapse_sublist(self):
        return self._synapse_sublist
    
    @property
    def label(self):
        """ The label of the subedge

        :return: The name, or None if there is no label
        :rtype: str
        :raise None: Raises no known exceptions
        """
        if self._synapse_sublist is None:
            associated_edge = \
                graph_mapper.get_partitionable_edge_from_partitioned_edge(self)
            
            return associated_edge.label
        else:
            return None
