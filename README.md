# CALC
CALC is software for generating convolutional network architectures that closely resemble the architecture of the primate visual cortex. Each layer in a CALC architecture corresponds with a cell population in the brain, specifically with the group of excitatory cells in a certain layer of a certain cortical area. Hyperparameters are optimized to match primate tract tracing data, cortical area sizes and cell densities, neuron-level in-degrees, and classical receptive field sizes where available. 

CALC was used to develop a convolutional architecture that matches a single hemisphere of the macaque monkey visual cortex, which we call the macaque single-hemisphere (MSH-CALC) model. Connections in this model are summarized in the diagram below. The colour indicates density of the connection. The density measure is the log-FLNe, or fraction of labelled neurons external to the injection site. This is a measure from retrograde tract-tracing studies that was used (among other data) to parameterize the architecture. 

![network diagram](https://github.com/bptripp/calc/blob/master/MSH-FLNe.png "network diagram")
