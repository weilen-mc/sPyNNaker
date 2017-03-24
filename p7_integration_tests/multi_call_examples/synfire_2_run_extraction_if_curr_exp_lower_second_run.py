"""
Synfirechain-like example
"""
import unittest

import spynnaker.plot_utils as plot_utils
import spynnaker.spike_checker as spike_checker

import p7_integration_tests.scripts.synfire_run_twice as synfire_run_twice

class Synfire2RunExtractionIfCurrExpLower(unittest.TestCase):
    def test_run(self):
        nNeurons = 200  # number of neurons in each population
        results = synfire_run_twice.do_run(nNeurons, second_run_multiple=0.5)
        (v1, gsyn1, spikes1, v2, gsyn2, spikes2) = results
        # print len(spikes1)
        # print len(spikes2)
        # plot_utils.plot_spikes(spikes1, spikes2)
        # plot_utils.heat_plot(v1, title="v1")
        # plot_utils.heat_plot(gsyn1, title="gysn1")
        # plot_utils.heat_plot(v2, title="v2")
        # plot_utils.heat_plot(gsyn2, title="gysn2")
        self.assertEquals(53, len(spikes1))
        self.assertEquals(103, len(spikes2))
        spike_checker.synfire_spike_checker(spikes1, nNeurons)
        spike_checker.synfire_multiple_lines_spike_checker(spikes2, nNeurons, 2)



if __name__ == '__main__':
    nNeurons = 200  # number of neurons in each population
    results = synfire_run_twice.do_run(nNeurons, second_run_multiple=0.5)
    (v1, gsyn1, spikes1, v2, gsyn2, spikes2) = results
    print len(spikes1)
    print len(spikes2)
    plot_utils.plot_spikes(spikes1, spikes2)
    plot_utils.heat_plot(v1, title="v1")
    plot_utils.heat_plot(gsyn1, title="gysn1")
    plot_utils.heat_plot(v2, title="v2")
    plot_utils.heat_plot(gsyn2, title="gysn2")