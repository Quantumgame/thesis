from __future__ import division

import sys
import os
if os.path.exists('../imtools/'):
    # sys.path.append('../imtools/')
    sys.path.insert(0, '../imtools/')
    from imtools import tools, misc
else:
    print 'You need to import package imtools: https://github.com/mjirik/imtools'
    sys.exit(0)

if os.path.exists('../mrf_segmentation/'):
    # sys.path.append('../imtools/')
    sys.path.insert(0, '../mrf_segmentation/')
    from mrfsegmentation.markov_random_field import MarkovRandomField


import matplotlib.pyplot as plt
import numpy as np
import skimage.exposure as skiexp
import scipy.stats as scista

import saliency_akisato as salaki
import saliency_google as salgoo
import saliency_ik as salik
import saliency_mayo as salmay
import copy

import datetime

verbose = False  # whether to write debug comments or not


def set_verbose(val):
    global verbose
    verbose = val


def _debug(msg, msgType="[INFO]"):
    if verbose:
        print '{} {} | {}'.format(msgType, msg, datetime.datetime.now())


def run(im, mask, alpha=1, beta=1, scale=0.5, show=False, show_now=True, verbose=True):
    # scale = 0.5  # scaling parameter for resizing the image
    # alpha = 1  # parameter for weighting the smoothness term (pairwise potentials)
    # beta = 1  # parameter for weighting the data term (unary potentials)

    set_verbose(verbose)

    _debug('Calculating saliency maps...')
    im_orig, image, salaki_map = salaki.run(im, mask)
    im_orig, image, salgoo_map = salgoo.run(im, mask=mask)
    im_orig, _, salik_map = salik.run(im, mask=mask, smoothing=True)
    im_orig, image, salmay_map = salmay.run(im, mask=mask, smoothing=True)

    # inverting intensity so that the tumor has high saliency
    salgoo_map = np.where(salgoo_map, 1 - salgoo_map, 0)
    # salik_map = skiexp.rescale_intensity(salik_map, out_range=(0, 1))

    saliencies = [salaki_map, salgoo_map, salik_map, salmay_map]
    tits = ['akisato', 'google', 'ik', 'mayo']
    # saliencies = [salaki_map, salgoo_map, salmay_map]
    # tits = ['akisato', 'google', 'mayo']

    # plt.figure()
    # for i, (im, tit) in enumerate(zip(saliencies, tits)):
    #     # plt.subplot(2, 2, i+1), plt.imshow(skiexp.rescale_intensity(im, out_range=(0, )), 'gray', interpolation='nearest')
    #     plt.subplot(2, 2, i+1), plt.imshow(im, 'gray', interpolation='nearest')
    #     plt.colorbar()
    #     plt.title(tit)
    # plt.show()

    im_bb, mask_bb = tools.crop_to_bbox(im, mask)

    im_bb = tools.smoothing(im_bb, sliceId=0)

    _debug('Creating MRF object...')
    mrf = MarkovRandomField(im_bb, mask=mask_bb, models_estim='hydohy', alpha=alpha, beta=beta, scale=scale, verbose=False)
    mrf.params['unaries_as_cdf'] = 1
    mrf.params['perc'] = 30
    mrf.params['domin_simple_estim'] = 0
    mrf.params['prob_w'] = 0.1

    # mrf.set_unaries(mrf.get_unaries())
    unaries, probs = mrf.get_unaries(ret_prob=True)

    unaries_l = [unaries[:, :, x].reshape(im_bb.shape) * mask_bb for x in range(unaries.shape[-1])]
    probs_l = [probs[:, :, x].reshape(im_bb.shape) * mask_bb for x in range(probs.shape[-1])]

    if show:
        tools.arange_figs(unaries_l, tits=['unaries hypo', 'unaries domin', 'unaries hyper'], max_r=1, colorbar=True, same_range=False, show_now=False)
        tools.arange_figs(probs_l, tits=['prob hypo', 'prob domin', 'prob hyper'], max_r=1, colorbar=True, same_range=False, show_now=True)

    res = mrf.run(resize=False)
    res = res[0, :, :]
    res = np.where(mask_bb, res, -1) + 1

    # plt.figure()
    # plt.subplot(121), plt.imshow(im_bb, 'gray'), plt.colorbar()
    # plt.subplot(122), plt.imshow(res, 'jet', interpolation='nearest')
    # plt.colorbar(ticks=range(mrf.n_objects + 1))
    # # mrf.plot_models(show_now=False)
    # plt.show()

    # plt.figure()
    # plt.subplot(221), plt.imshow(im_orig, 'gray', interpolation='nearest'), plt.title('input')
    # plt.subplot(222), plt.imshow(res, interpolation='nearest'), plt.title('result')
    # plt.subplot(223), plt.imshow(mrf.get_unaries[:, 0, 0].reshape(im_orig.shape), 'gray', interpolation='nearest')
    # plt.colorbar(), plt.title('unary #1')
    # plt.subplot(224), plt.imshow(mrf.get_unaries[:, 0, 1].reshape(im_orig.shape), 'gray', interpolation='nearest')
    # plt.colorbar(), plt.title('unary #2')
    # plt.show()

    unary_domin = mrf.get_unaries()[:, :, 1]
    max_prob = unary_domin.max()

    # plt.figure()
    # plt.subplot(121), plt.imshow(im_bb, 'gray')
    # plt.subplot(122), plt.imshow(unary_domin.reshape(im_bb.shape), 'gray', interpolation='nearest')
    # plt.show()

    # rescaling intensities
    # max_int = 0.5
    max_int = max_prob
    saliencies_inv = []
    for i, im in enumerate(saliencies):
        saliencies[i] = skiexp.rescale_intensity(im, out_range=(0, max_int)).astype(unary_domin.dtype)
        saliencies_inv.append(skiexp.rescale_intensity(im, out_range=(max_int, 0)).astype(unary_domin.dtype))

    # if scale != 0:
    #     for i, im in enumerate(saliencies):
    #         saliencies[i] = tools.resize3D(im, scale, sliceId=0)

    # unaries_domin_sal = [np.dstack((unary_domin, skiexp.rescale_intensity(x, out_range=(x.max(), x.min())).astype(unary_domin.dtype).reshape(-1, 1))) for x in saliencies]
    unaries_domin_sal = [np.dstack((y.reshape(-1, 1), x.reshape(-1, 1))) for y, x in zip(saliencies, saliencies_inv)]

    results = []
    alpha = 1
    beta = 1
    mrf = MarkovRandomField(im_bb, mask=mask_bb, models_estim='hydohy', alpha=alpha, beta=beta, scale=scale, verbose=False)
    for i, unary in enumerate(unaries_domin_sal):
        _debug('Optimizing MRF with unary term: %s' % tits[i])
        # mrf.set_unaries(unary.astype(np.int32))
        mrf.alpha = alpha
        mrf.beta = beta
        mrf.models = []
        mrf.set_unaries(unary)
        res = mrf.run(resize=False)
        results.append(res.copy())

        plt.figure()
        plt.subplot(221), plt.imshow(im_orig, 'gray', interpolation='nearest'), plt.title('input')
        plt.subplot(222), plt.imshow(res[0, :, :], interpolation='nearest'), plt.title('result')
        plt.subplot(223), plt.imshow(unary[:, 0, 0].reshape(im_orig.shape), 'gray', interpolation='nearest')
        plt.colorbar(), plt.title('unary #1')
        plt.subplot(224), plt.imshow(unary[:, 0, 1].reshape(im_orig.shape), 'gray', interpolation='nearest')
        plt.colorbar(), plt.title('unary #2')
        plt.show()

    # mrf.set_unaries(unaries)
    # unaries =
    # mrf.run()
    # return mrf.labels_orig

    plt.figure()
    n_imgs = 1 + len(saliencies)
    plt.subplot(2, n_imgs, 1)
    plt.imshow(im_orig, 'gray', interpolation='nearest'), plt.title('input')
    for i in range(len(saliencies)):
        plt.subplot(2, n_imgs, i + 2)
        plt.imshow(saliencies[i], 'gray', interpolation='nearest')
        plt.title(tits[i])
    for i, r in enumerate(results):
        plt.subplot(2, n_imgs, i + n_imgs + 2)
        plt.imshow(results[i][0, :, :], interpolation='nearest'), plt.title('result - %s' % tits[i])
    plt.show()

#-----------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------
if __name__ == '__main__':
    data_fname = '/home/tomas/Data/medical/liver_segmentation/org-exp_183_46324212_venous_5.0_B30f-.pklz'
    data, mask, voxel_size = tools.load_pickle_data(data_fname)

    slice_ind = 17
    data_s = data[slice_ind, :, :]
    data_s = tools.windowing(data_s)
    mask_s = mask[slice_ind, :, :]

    run(data_s, mask_s, alpha=50)

    # im_o, img, saliency = run(data_s, mask_s, show=False)
    # im_o_s, img_s, saliency_s = run(data_s, mask_s, smoothing=True, show=False)
    #
    # plt.figure()
    # plt.subplot(231), plt.imshow(im_o, 'gray', interpolation='nearest'), plt.title('input')
    # plt.subplot(233), plt.imshow(saliency, 'gray', interpolation='nearest'), plt.title('saliency map')
    #
    # plt.subplot(234), plt.imshow(im_o_s, 'gray', interpolation='nearest'), plt.title('input')
    # plt.subplot(235), plt.imshow(img_s, 'gray', interpolation='nearest'), plt.title('smoothed')
    # plt.subplot(236), plt.imshow(saliency_s, 'gray', interpolation='nearest'), plt.title('saliency')
    # plt.show()