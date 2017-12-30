# CALC
CALC is software for generating convolutional network architectures that closely resemble the architecture of the primate cortex. Each layer in a CALC architecture corresponds with a cell population in the brain, specifically with the group of excitatory cells in a certain layer of a certain cortical area. Hyperparameters are optimized to match primate tract tracing data, cortical area sizes and cell densities, neuron-level in-degrees, and classical receptive field sizes where available. 

It is a work in progress.

## Source Data
In addition to the code, you will also need some data files that are not redistributed here, described in the following subsections. When you have all the files, run check_data() in data.py to make sure everything is as expected.

### Core-Nets
Register on core-nets.org, and download the following files:

JCN_2013 Table.xls

Cercor_2012 Table.xls

Open each of these files, and save the first sheet in .csv format, in the calc/data/markov folder.

### BALSA
Go to https://balsa.wustl.edu/study/show/W336 and click the Download button. You will need the following files: 

MacaqueYerkes19.R.midthickness.32k_fs_LR.surf.gii

MacaqueYerkes19.R.very_inflated.32k_fs_LR.surf.gii

MarkovCC12_M132_91-area.32k_fs_LR.dlabel.nii

### CoCoMac 2.0
Download a JSON file of CoCoMac data with information about the source and target layers of inter-area connections. The direct link to the query result is: http://cocomac.g-node.org/services/connectivity_matrix.php?dbdate=20141022&AP=AxonalProjections_FV91&constraint=&origins=&terminals=&square=1&merge=max&laminar=both&format=json&cite=1 Save the result as connectivity_data.json in the calc/data_files/cocomac folder. 

If you publish work that uses CoCoMac (which is likely if you publish something that uses CALC) you must cite Bakker et al. (2012) (https://www.frontiersin.org/articles/10.3389/fninf.2012.00030/full) and the relevant original tract tracing studies. You can find references to the the relevant tract tracing studies by cortical area, from the CoCoMac query interface, but it is a multi-step process. For convenience, references for some areas are listed in calc/data_files/cocomac/cocomac.bib. To find them yourself, the first step is to go to http://cocomac.g-node.org/services/search_wizard.php and set up a query that looks like this (note this example is for the lateral intraparietal area, LIP): 

Type of data to search for: AxonalProjections_FV91

Apply a constraint: Yes

Property to limit search by: BrainMaps_BrainSites.BrainSite

Use operator: equals

Use value: FV91-LIP

Add another constraint: No 

Limit number of results to: 500

Start at result page: 1

Output format: dynamic table

You don’t need the results of the query, but you do need the URL of the results page. Select and copy it. Then go to http://cocomac.g-node.org/services/connectivity_matrix.php and set up the query on this page as follows: 

Database version: release 2014 Oct. 22

Axonal projections table: AxonalProjections_FV91

Search wizard URL to constrain rows of this table: http://cocomac.g-node.org/services/search_wizard.php?T=AxonalProjections_FV91&x0=WHERE&L0=%5Eaxon_terminal.BrainSite&op0=eq&R0=FV91-LIP&x1=&limit=500&page=1&format=dhtml

Generate square matrix: Yes ...

Merge multiple reports: Take the maximum value

Show laminar patterns: Both origin and terminal, as json array

Output format: html table

Indicate that you will abide by our citation policy: Yes ... 

The URL you copied from the previous query should be pasted into the “Search wizard URL ..." box. Click the “Generate connectivity matrix” button. The reference codes will be listed at the bottom of the results. Full information on each reference can be found at http://cocomac.g-node.org/services/search_wizard.php?T=Literature&x0=&limit=500&page=1&format=dhtml 

