from __future__ import division

import numpy as np
import matplotlib.pyplot as plt

import skimage.segmentation as skiseg
import skimage.measure as skimea

import scipy.ndimage.measurements as scindimea

# import tools
import os
import sys
if os.path.exists('../imtools/'):
    sys.path.append('../imtools/')
    from imtools import tools
else:
    print 'You need to import package imtools: https://github.com/mjirik/imtools'
    sys.exit(0)

import sys

def rw_segmentation(im, seeds, slicewise):
    if slicewise:
        seg = np.zeros_like(seeds)
        for i, (im_s, seeds_s) in enumerate(zip(im, seeds)):
            seg[i, :, :] = skiseg.random_walker(im_s, seeds_s)
    else:
        seg = skiseg.random_walker(im, seeds)

    return seg


# def run_slicewise(data, seeds, mask=None, separe=False, bg_lbl=1):
#     if separe:
#         bg = data == bg_lbl
#
#
#         bg_lbls, n_bgs = scindimea.label(data)
#         for i in range(n_bgs):
#             bg = bg_lbls == i + 1
#             props = skimea.regionprops(bg)


def run(data, seeds, mask=None, separe=True, bg_lbl=1, slicewise=True):
    segs = None

    if isinstance(seeds, str):
        seeds = np.load(seeds)

    if separe:
        bg = data == bg_lbl

        bg_lbls, n_bgs = scindimea.label(seeds==1, structure=np.ones((3, 3, 3)))

        # deriving bboxes
        bboxes = []
        for i in range(n_bgs):
            bg = bg_lbls == i + 1
            # s_min, s_max, r_min, r_max, c_min, c_max = tools.get_bbox(bg)
            bbox = tools.get_bbox(bg)
            bboxes.append(bbox)

        # segmentation
        segs = np.zeros_like(data)
        for bbox in bboxes:
            im_cr = data[bbox[0]:bbox[1] + 1, bbox[2]:bbox[3] + 1, bbox[4]:bbox[5] + 1]
            seeds_cr = seeds[bbox[0]:bbox[1] + 1, bbox[2]:bbox[3] + 1, bbox[4]:bbox[5] + 1]

            seg = rw_segmentation(im_cr, seeds_cr, slicewise) - 1
            segs[bbox[0]:bbox[1] + 1, bbox[2]:bbox[3] + 1, bbox[4]:bbox[5] + 1] += seg

            # data visualization
            # tools.show_3d((im_cr, seg))
            # tools.show_3d((data, segs))

    return segs