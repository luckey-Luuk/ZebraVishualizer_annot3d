# -*- coding: utf-8 -*-
"""
Created on Mon Aug  8 17:41:00 2022

@author: 13784
"""
import pickle

def open_track_dictionary(save_file):
    pickle_in = open(save_file,"rb")
    dictionary = pickle.load(pickle_in)
    return dictionary

# tracksavedir = "F://Cell tracking//3D cell segmentation//10 tracking code//final pkl file//"
tracksavedir = "Data/3D tracking data to visualize/"

refdistance8 = open_track_dictionary(tracksavedir + "refdistance_29layer_linkage.pkl")
print(refdistance8["20190701--2"])
