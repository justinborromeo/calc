"""
This file contains code related to setting stride hyperparameters. The other
hyperparameters are optimized using gradient descent, and rounded if they are
supposed to be integers. However, this doesn't work well for strides. Because
they are integers that have small optimal values, optimizing as floats and rounding
can cause problems such as large quantization error, inconsistency between
converging paths, and strides of 0.

To avoid these problems, we choose random candidate stride patterns, and then
optimize other parameters using gradient descent. We partially optimize the
other hyperparameters of a number of candidates and choose the one with the best
result. The algorithm is as follows:

1: Start by setting all strides to None
2: While at least one stride is None:
2.1: Find longest path within network that consists only of edges with None strides
2.2: Set strides along longest path
2.3: If cumulative stride along path is greater than image width or doesn't equal
    gain from start to end (if cumulative strides at each end are known) return to 2.1

TODO: do we need to enumerate all options or just try random ones?
TODO: This code assumes the network has a single input.
"""

import numpy as np
import networkx as nx
import calc.conversion
import calc.system, calc.network
from calc.data import areas_FV91, E07


def get_stride_pattern(system, max_cumulative_stride=32, best_of=50):
    best_distance = 1e10
    best_pattern = None

    for i in range(best_of):
        print('Making stride pattern {} of {}'.format(i, best_of))
        candidate = StridePattern(system, max_cumulative_stride)
        candidate.set_hints()
        candidate.fill()
        distance = candidate.distance_from_hints()
        if distance < best_distance:
            best_distance = distance
            best_pattern = candidate

    return best_pattern

class StridePattern:

    def __init__(self, system, max_cumulative_stride):
        """
        Initializes a stride-pattern candidate with null strides.

        :param system: the System for which candidate strides are to be proposed
        :param max_cumulative_stride: maximum cumulative stride through the system along
            any feedforward path; this would nornally be the resolution of the
            input image, to prevent later feature maps from having less than
            one-pixel resolution
        """

        self.system = system
        self.max_cumulative_stride = max_cumulative_stride

        self.strides = [None] * len(system.projections)
        self.cumulatives = [None] * len(system.populations)
        self.cumulative_hints = [None] * len(system.populations)
        self.min_cumulatives = [1] * len(system.populations)
        self.max_cumulatives = [max_cumulative_stride] * len(system.populations)

        input_index = system.find_population_index(system.input_name)
        self.cumulatives[input_index] = 1

    def set_hints(self, image_layer=0, image_channels=3, V1_channels=120, other_channels={'LGNparvo': 4, 'LGNmagno': 2, 'LGNkonio': 1}):
        # inferred from spine counts

        image_pixels = np.sqrt(system.populations[image_layer].n / image_channels)

        e07 = E07()
        V1_spine_count = e07.get_spine_count('V1')

        for i in range(len(self.system.populations)):
            pop = self.system.populations[i]
            area = pop.name.split('_')[0]
            if i == image_layer:
                channels = image_channels
            if pop.name in other_channels.keys():
                channels = other_channels[pop.name]
            elif area in areas_FV91:
                spine_count = e07.get_spine_count(area)
                channels = np.round(V1_channels * spine_count / V1_spine_count)

            pixels = np.sqrt(pop.n / channels)
            self.cumulative_hints[i] = image_pixels / pixels

    def distance_from_hints(self):
        total = 0
        for i in range(len(self.cumulative_hints)):
            error = np.log(self.cumulatives[i] / self.cumulative_hints[i])**2
            total += error
        return np.sqrt(total / len(self.cumulative_hints))

    def _update_cumulative_stride_bounds(self):
        graph = self.system.make_graph()

        for i in range(len(self.system.populations)):
            pop = self.system.populations[i]

            # cumulative stride can't be less than that of ancestors
            ancestors = nx.ancestors(graph, pop.name)
            for ancestor in ancestors:
                ancestor_index = self.system.find_population_index(ancestor)
                if self.cumulatives[ancestor_index] is not None:
                    self.min_cumulatives[i] = max(self.min_cumulatives[i], self.cumulatives[ancestor_index])

            # cumulative stride can't be greater than that of descendants
            descendants = nx.descendants(graph, pop.name)
            for descendant in descendants:
                descendant_index = self.system.find_population_index(descendant)
                if self.cumulatives[descendant_index] is not None:
                    self.max_cumulatives[i] = min(self.max_cumulatives[i], self.cumulatives[descendant_index])

    def fill(self):
        """
        Fills in None strides in the network with candidate values.
        """

        while max([x is None for x in self.strides]):
            path = self._longest_unset_path()
            # print('Setting strides for path: {}'.format(path))

            start_cumulative = self.cumulatives[self.system.find_population_index(path[0])]
            end_cumulative = self.cumulatives[self.system.find_population_index(path[-1])]

            steps = len(path) - 1
            max_stride = StridePattern._get_max_stride(self.max_cumulative_stride, steps)

            if end_cumulative is not None:
                if start_cumulative is not None:
                    max_stride = StridePattern._get_max_stride(end_cumulative / start_cumulative, steps)
                else:
                    max_stride = StridePattern._get_max_stride(end_cumulative, steps)

            # print('start c: {} end c: {} max c: {} max stride: {} len: {}'.format(
            #     start_cumulative, end_cumulative, self.max_cumulative_stride, max_stride, len(path)-1))
            self.init_path(path, exact_cumulative=end_cumulative, max_stride=max_stride)
            self._update_cumulative_stride_bounds()

    @staticmethod
    def _get_max_stride(cumulative_stride, steps):
        return int(2 * np.floor(cumulative_stride ** (1 / steps)))

    def _longest_unset_path(self):
        """
        :return: Longest path through the network that includes only connections for which
            the stride has not yet been determined for this StridePattern
        """
        graph = self.system.make_graph()

        for i in range(len(self.system.projections)):
            if self.strides[i] is not None:
                origin = self.system.projections[i].origin.name
                termination = self.system.projections[i].termination.name
                graph.remove_edge(origin, termination)

        return nx.algorithms.dag.dag_longest_path(graph)

    def init_path(self, path, exact_cumulative=None, min_stride=1, max_stride=3, max_attempts=10000):
        """
        Sets strides along the path to integer values between min_stride and
        max_stride. Strides are sampled at random, and rejected if the
        cumulative stride along the path (product of all strides) is greater than
        max_cumulative, and/or not equal to exact_cumulative (if this is not None).
        This method does not change strides that have been set previously.

        :param path: a path, in the form of a list of node names, along which to choose random strides
        :param exact_cumulative (default None): if not None, defines the exact cumulative stride
            required at the end of the path (for consistency with other strides in the network)
        :param min_stride (default 1): minimum random stride value
        :param max_stride (default 3): maximum random stride value
        """

        done = False

        for attempt in range(max_attempts):
            # make copies in case we have to revert
            strides = self.strides[:]
            cumulatives = self.cumulatives[:]

            failed = False

            for i in range(len(path) - 1):
                projection_ind = self.system.find_projection_index(path[i], path[i+1])
                pre_ind = self.system.find_population_index(path[i])
                post_ind = self.system.find_population_index(path[i+1])

                if self.cumulatives[post_ind] and self.cumulatives[pre_ind]:
                    #TODO: deal with non-integers here by failing
                    strides[projection_ind] = self.cumulatives[post_ind] / self.cumulatives[pre_ind]
                else:
                    strides[projection_ind] = self._sample_stride(pre_ind, post_ind, min_stride, max_stride)
                    # strides[projection_ind] = np.random.randint(min_stride, max_stride+1)
                    cumulatives[post_ind] = cumulatives[pre_ind] * strides[projection_ind]

                    # print('setting {} <= {} <= {} for {}'.format(self.min_cumulatives[post_ind], cumulatives[post_ind], self.max_cumulatives[post_ind], system.populations[post_ind].name))
                    if cumulatives[post_ind] > self.max_cumulatives[post_ind] \
                            or cumulatives[post_ind] < self.min_cumulatives[post_ind]:
                        # print('...nope')
                        failed = True
                        break

            if not failed:
                end_cumulative = cumulatives[self.system.find_population_index(path[-1])]
                if exact_cumulative is None or exact_cumulative == end_cumulative:
                    self.strides = strides
                    self.cumulatives = cumulatives
                    done = True
                    break

        if not done:
            print('initialization failed; exact cumulative {}, min {}, max {}'.format(exact_cumulative, min_stride, max_stride))

    def _sample_stride(self, pre_ind, post_ind, min_stride, max_stride):
        possible_strides = range(min_stride, max_stride + 1)

        if self.cumulative_hints[pre_ind] and self.cumulative_hints[post_ind]:
            stride_hint = self.cumulative_hints[post_ind] / self.cumulative_hints[pre_ind]
            relative_probabilities = [1/(.1+np.abs(stride-stride_hint))**2 for stride in possible_strides]
            probabilities = relative_probabilities / np.sum(relative_probabilities)
        else:
            probabilities = None

        result = np.random.choice(possible_strides, p=probabilities)

        # print('******')
        # print(possible_strides)
        # print(probabilities)
        # print(result)

        return result


def initialize_network(system, candidate, image_layer=0, image_channels=3.):
    """
    :param system TODO
    :param candidate TODO
    :param image_layer TODO
    :param image_channels TODO
    :return: A neural network architecture with the same nodes and connections as the given
        neurophysiological system architecture, the given stride pattern, with other
        hyperparameters initialized randomly.
    """
    net = calc.network.Network()

    approx_image_resolution = np.sqrt(system.populations[image_layer].n/image_channels)
    max_cumulative_stride = np.max(candidate.cumulatives)
    image_resolution = round(approx_image_resolution / max_cumulative_stride) * max_cumulative_stride

    for i in range(len(system.populations)):
        pop = system.populations[i]

        if i == image_layer:
            channels = image_channels
            pixels = image_resolution
        else:
            pixels = image_resolution / candidate.cumulatives[i]
            channels = max(1, round(pop.n / pixels**2))

        net.add(pop.name, channels, pixels)

    for i in range(len(system.projections)):
        projection = system.projections[i]
        pre = net.find_layer(projection.origin.name)
        post = net.find_layer(projection.termination.name)

        stride = candidate.strides[i]

        c = .1 + .2*np.random.rand()
        sigma = .1 + .1*np.random.rand()

        #TODO: this is reset in conversion
        w = 7

        net.connect(pre, post, c, stride, w, sigma)

    return net

    # def estimate_by_spine_density(self, V1_channels=120):
    #     #TODO: only works with FV91
    #     for i in range(len(self.system.populations)):
    #         pop = self.system.populations
    #         area = pop.name.split('_')[0]
    #         if area == 'V1':
    #             self.cumulatives




# def initialize_network_via_spine_count(system, image_layer=0, image_channels=3., V1_channels=120, other_channels=None):
#     e07 = E07()
#     net = calc.network.Network()
#     image_resolution = np.sqrt(system.populations[image_layer].n/image_channels)
#
#     for i in range(len(system.populations)):
#         pop = system.populations[i]
#
#         V1_spine_count = e07.get_spine_count('V1')
#
#         if i == image_layer:
#             channels = image_channels
#             pixels = image_resolution
#         else:
#             area = pop.name.split('_')[0]
#             spine_count = e07.get_spine_count(area)
#             channels = np.round(V1_channels * spine_count / V1_spine_count)
#
#             pixels = image_resolution / candidate.cumulatives[i]
#             channels = max(1, round(pop.n / pixels**2))
#
#         net.add(pop.name, channels, pixels)
#
#     for i in range(len(system.projections)):
#         projection = system.projections[i]
#         pre = net.find_layer(projection.origin.name)
#         post = net.find_layer(projection.termination.name)
#
#         stride = candidate.strides[i]
#
#         c = .1 + .2*np.random.rand()
#         sigma = .1 + .1*np.random.rand()
#
#         #TODO: this is reset in conversion
#         w = 7
#
#         net.connect(pre, post, c, stride, w, sigma)
#
#     return net


if __name__ == '__main__':
    # system = calc.system.get_example_small()
    system = calc.system.get_example_medium()
    # path = longest_path(system, 'V4_5')
    # print(path)

    candidate = get_stride_pattern(system)
    # candidate = StridePattern(system, 32)
    # candidate.set_hints()
    # candidate.fill()

    # print(candidate.strides)
    print(candidate.cumulatives)
    for i in range(len(system.populations)):
        print('{}: {} vs {}'.format(system.populations[i].name, candidate.cumulatives[i], candidate.cumulative_hints[i]))
    #
    # print('distance from hints: {}'.format(candidate.distance_from_hints()))

    net = initialize_network(system, candidate, image_layer=0, image_channels=3.)
    net.print()

    # net, training_curve = calc.conversion.test_stride_pattern(system)
    # import matplotlib.pyplot as plt
    # plt.semilogy(training_curve)
    # plt.show()

    # calc.conversion.test_stride_patterns(system)

    # candidate.init_path(path)
    #
    # for i in range(len(system.projections)):
    #     projection = system.projections[i]
    #     print('{}->{}: {}'.format(projection.origin.name, projection.termination.name, candidate.strides[i]))
    #
    # print(candidate.longest_unset_path())
