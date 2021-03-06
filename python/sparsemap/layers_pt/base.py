import numpy as np

import torch
from torch.autograd import Variable, Function

from .. import sparsemap
from ..utils import S_from_Ainv


class _BaseSparseMarginals(Function):

    def __init__(self, max_iter=10, verbose=0):
        self.max_iter = max_iter
        self.verbose = verbose

    def forward(self, unaries):

        cuda_device = None
        if unaries.is_cuda:
            cuda_device = unaries.get_device()
            unaries = unaries.cpu()

        factor = self.build_factor()
        u, _, status = sparsemap(factor, unaries, [],
                                 max_iter=self.max_iter,
                                 verbose=self.verbose)
        self.status = status

        out = torch.from_numpy(u)
        if cuda_device is not None:
            out = out.cuda(cuda_device)
        return out

    def _d_vbar(self, M, dy):

        Ainv = torch.from_numpy(self.status['inverse_A'])
        S = S_from_Ainv(Ainv)

        if M.is_cuda:
            S = S.cuda()
        # B = S11t / 1S1t
        # dvbar = (I - B) S M dy

        # we first compute S M dy
        first_term = S @ (M @ dy)
        # then, BSMt dy = B * first_term. Optimized:
        # 1S1t = S.sum()
        # S11tx = (S1) (1t * x)
        second_term = (first_term.sum() * S.sum(0)) / S.sum()
        d_vbar = first_term - second_term
        return d_vbar


    def backward(self, dy):
        cuda_device = None

        if dy.is_cuda:
            cuda_device = dy.get_device()
            dy = dy.cpu()

        M = torch.from_numpy(self.status['M'])

        d_vbar = self._d_vbar(M, dy)
        d_unary = M.t() @ d_vbar

        if cuda_device is not None:
            d_unary = d_unary.cuda(cuda_device)

        return d_unary


class _BaseSparseMarginalsAdditionals(_BaseSparseMarginals):

    def forward(self, unaries, additionals):

        cuda_device = None
        if unaries.is_cuda:
            cuda_device = unaries.get_device()
            unaries = unaries.cpu()
            additionals = additionals.cpu()

        factor = self.build_factor()
        u, uadd, status = sparsemap(factor, unaries, additionals,
                                    max_iter=self.max_iter,
                                    verbose=self.verbose)

        self.status = status

        out = torch.from_numpy(u)
        if cuda_device is not None:
            out = out.cuda(cuda_device)
        return out

    def backward(self, dy):
        cuda_device = None

        if dy.is_cuda:
            cuda_device = dy.get_device()
            dy = dy.cpu()

        M = torch.from_numpy(self.status['M'])
        Madd = torch.from_numpy(self.status['Madd'])
        if dy.is_cuda:
            M = M.cuda()
            Madd = Madd.cuda()

        d_vbar = self._d_vbar(M, dy)
        d_unary = M.t() @ d_vbar
        d_additionals = Madd.t() @ d_vbar

        if cuda_device is not None:
            d_unary = d_unary.cuda(cuda_device)
            d_additionals = d_additionals.cuda(cuda_device)

        return d_unary, d_additionals
