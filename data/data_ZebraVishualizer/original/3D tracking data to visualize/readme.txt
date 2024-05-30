1. The folder: 20190701--2_inter_29layers_green
29-layer interpolation data from 8-layer raw data

2. The folder: 20190701--2_inter_29layers_mask_3a
is the corresponding segmentation mask data of 29-layer interpolation data;
each cell on each frame was labeled with different IDs, you can open the image with "Fiji/imageJ" software, put the cursor on each cell, you can see the intensity values which represent the cell ID. 

3. refdistance_29layer_linkage.pkl
the trajectories obtained from algorithms were saved in this pkl file

4. read pkl file.py
use this python code to read the trajectories which saved in pkl file;
you will find: There are different "Key", which represents different image stack.
Just select the value in "20190701--2", it is coresponded to the image stack "20190701--2_inter_29layers_green";
 50 trajectories were saved in list format.

The trajectory was saved in a group of tuple structures:
such as: [(1,0,-1), (1,1,1), (1,2,3)............]

the middle value 0, 1, 2, represent the frame numbers;
the first value represents: the cell ID on current frame;
the second value represents: the cell ID which need to be linked in the previous frame.

(1, 0, -1): -1 on the first frame represents there was no linkage before frame 1.

tips: the mask data used to help finding the corresponding IDs, then associate the trajectory from the generated tracks in pkl file.
