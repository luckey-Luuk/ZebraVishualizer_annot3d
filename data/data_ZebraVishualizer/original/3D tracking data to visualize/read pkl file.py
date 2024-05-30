# -*- coding: utf-8 -*-
"""
Created on Mon Aug  8 17:41:00 2022

@author: 13784
"""
import pickle
import os

def open_track_dictionary(save_file):
    pickle_in = open(save_file,"rb")
    dictionary = pickle.load(pickle_in)
    return dictionary

# tracksavedir = "C:/Users/Eigenaar/Documents/universiteit/Bachelor eindproject/git/ZebraVishualizer_annot3d/data_ZebraVishualizer/original/3D tracking data to visualize/"
tracksavedir = os.path.dirname(__file__)

# refdistance8 = open_track_dictionary(tracksavedir + "refdistance_29layer_linkage.pkl")
refdistance8 = open_track_dictionary(os.path.join(tracksavedir, "refdistance_29layer_linkage.pkl"))
print(refdistance8["20190701--2"])
