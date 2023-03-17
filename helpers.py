from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import os

# from skimage draw
def disk(center, radius, *, shape=None):
  radii = np.array([radius, radius])

  upper_left = np.ceil(center - radii).astype(int)
  upper_left = np.maximum(upper_left, np.array([0, 0]))

  lower_right = np.floor(center + radii).astype(int)
  lower_right = np.minimum(lower_right, np.array(shape[:2]) - 1)

  shifted_center = center - upper_left
  bounding_shape = lower_right - upper_left + 1

  r_lim, c_lim = np.ogrid[0:float(bounding_shape[0]), 0:float(bounding_shape[1])]
  r_org, c_org = shifted_center
  r_rad, c_rad = radii

  r, c = (r_lim - r_org), (c_lim - c_org)
  distances = (r / r_rad) ** 2 + (-c / c_rad) ** 2
  rr, cc = np.nonzero(distances < 1)

  rr.flags.writeable = True
  cc.flags.writeable = True
  rr += upper_left[0]
  cc += upper_left[1]

  return rr, cc



def read_tiff(path): # returns tiff image stack as np array
    img = Image.open(path)
    xy = []
    xz = []
    yz = []

    for i in range(img.n_frames): #x-y plane
        img.seek(i)  
        
        new_img=img.convert('L')
        contrast=ImageEnhance.Contrast(new_img)
        contrast_img=contrast.enhance(5)
        contrast_img=contrast_img.filter(ImageFilter.MedianFilter(size=3))
        contrast_img=contrast_img.filter(ImageFilter.GaussianBlur(radius=2))

        xy.append(np.array(contrast_img)) #check if this works
        #xy.append(np.array(img))

    xy = np.array(xy)

    for npimg in np.swapaxes(xy, 0, 1): # x with z, x-z plane
        xz.append(npimg)

    for npimg in np.swapaxes(xy, 0, 2): # x with y, y-z plane
        yz.append(npimg)

    return xy, xz, yz


def apply_contrast(npslice, f):
    #minval = np.percentile(npslice, f) # vary threshold between 1st and 99th percentiles, when f=1
    minval=0#the lowest value will always be zero
    maxval = np.percentile(npslice, 101-f)#was 100-f is now 101-f
    result = np.clip(npslice, minval, maxval)
    #print(npslice[0][20])
    if np.any(result)==True:
        result = ((result - minval) / (maxval - minval)) * 1024
    return (result).astype(np.short)


def apply_brightness(npslice, f):
    return (npslice*f).astype(np.short)

def create_image_dict(directory="data"):#returns dictonary of image file names
    file_list=[]
    for file in os.listdir(directory):
        if file.endswith('.tif'):
            if '++' in file:
                file_list.append(file)
    
    file_list=sorted(file_list)
    file_dict={}
    for i in range(len(file_list)):
        file_dict[i]=file_list[i]
    return file_dict

#print(create_image_dict())
#test_array=[[[1,2,3],[4,5,6]],[[10,-2,-3],[-4,50,-6]],[[-11,-21,-31],[-41,-51,61]]]
#test_array=np.array(test_array)
#extract_max_value(test_array)