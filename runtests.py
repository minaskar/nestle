#!/usr/bin/env py.test
from __future__ import print_function, division

import math
from copy import deepcopy

import numpy as np
from numpy.random import RandomState
from numpy.testing import assert_allclose
import pytest

import nestle

NMAX = 20  # many tests are run for dimensions 1 to NMAX inclusive

def test_vol_prefactor():
    assert nestle.vol_prefactor(1) == 2.
    assert nestle.vol_prefactor(2) == math.pi
    assert nestle.vol_prefactor(3) == 4./3. * math.pi
    assert nestle.vol_prefactor(4) == 1./2. * math.pi**2
    assert nestle.vol_prefactor(5) == 8./15. * math.pi**2
    assert nestle.vol_prefactor(9) == 32./945. * math.pi**4


def test_rstate_kwarg():
    """Test that rstate keyword argument works as expected."""
    rstate = RandomState(123)
    a = nestle.randsphere(10, rstate=rstate)
    np.random.seed(123)
    b = nestle.randsphere(10)

    assert np.all(a == b)

# TODO: test that points are uniform
def test_randsphere():
    """Draw a lot of points and check that they're within a unit sphere.
    """
    rstate = RandomState(0)
    npoints = 1000
    
    for n in range(1, NMAX+1):
        for i in range(npoints):
            x = nestle.randsphere(n, rstate=rstate)
            r = np.sum(x**2)
            assert r < 1.0
        

@pytest.mark.skipif("not nestle.HAVE_CHOICE")
def test_random_choice():
    """nestle.random_choice() is designed to mimic np.random.choice(),
    for numpy < v1.7.0. In cases where we have both, test that they agree.
    """
    rstate = RandomState(0)
    p = rstate.rand(10)
    p /= p.sum()
    for seed in range(10):
        rstate.seed(seed)
        i = rstate.choice(10, p=p)
        rstate.seed(seed)
        j = nestle.random_choice(10, p=p, rstate=rstate)
        assert i == j


def test_ellipsoid_sphere():
    """Test that Ellipsoid works like a sphere when ``a`` is proportional to
    the identity matrix."""

    scale = 5.
    for n in range(1, NMAX+1):
        ctr = 2.0 * scale * np.ones(n)  # arbitrary non-zero center
        a = 1.0 / scale**2 * np.identity(n)
        ell = nestle.Ellipsoid(ctr, a)

        assert_allclose(ell.vol, nestle.vol_prefactor(n) * scale**n)
        assert_allclose(ell.axlens, scale * np.ones(n))
        assert_allclose(ell.axes, scale * np.identity(n))


def test_ellipsoid_vol_scaling():
    """Test that scaling an ellipse works as expected."""

    scale = 1.5 # linear scale

    for n in range(1, NMAX+1):
        # ellipsoid centered at origin with principle axes aligned with
        # coordinate axes, but random sizes.
        ctr = np.zeros(n)
        a = np.diag(np.random.rand(n))
        ell = nestle.Ellipsoid(ctr, a)

        # second ellipsoid with axes scaled.
        ell2 = nestle.Ellipsoid(ctr, 1./scale**2 * a)

        # scale volume of first ellipse to match the second.
        ell.scale_to_vol(ell.vol * scale**n)
        
        # check that the ellipses are the same.
        assert_allclose(ell.vol, ell2.vol)
        assert_allclose(ell.a, ell2.a)
        assert_allclose(ell.axes, ell2.axes)
        assert_allclose(ell.axlens, ell2.axlens)


def test_ellipsoid_contains():
    """Test Elipsoid.contains()"""
    eps = 1.e-7

    for n in range(1, NMAX+1):
        ell = nestle.Ellipsoid(np.zeros(n), np.identity(n))  # unit n-sphere
        
        # point just outside unit n-sphere:
        pt = (1. / np.sqrt(n) + eps) * np.ones(n)
        assert not ell.contains(pt)

        # point just inside unit n-sphere:
        pt = (1. / np.sqrt(n) - eps) * np.ones(n)
        assert ell.contains(pt)

        # non-equal axes ellipsoid, still aligned on axes:
        a = np.diag(np.random.rand(n))
        ell = nestle.Ellipsoid(np.zeros(n), a)

        # check points on axes
        for i in range(0, n):
            axlen = 1. / np.sqrt(a[i, i])  # length of this axis
            pt = np.zeros(n)
            pt[i] = axlen + eps
            assert not ell.contains(pt)
            pt[i] = axlen - eps
            assert ell.contains(pt)


def random_ellipsoid(n):
    """Return a random `n`-d ellipsoid centered at the origin

    This is a helper function for other tests.
    """

    # `a` in the ellipsoid must be positive definite, so we have to construct
    # a positive definite matrix. For any real, non-singular matrix A,
    # `A^T A` will be positive definite.
    det = 0.
    while abs(det) < 1.e-10:  # ensure a non-singular matrix
        A = np.random.rand(n, n)
        det = np.linalg.det(A)

    return nestle.Ellipsoid(np.zeros(n), np.dot(A.T, A))


def test_ellipsoid_sample():
    """Ensure that Ellipsoid.sample() returns samples in itself and make
    some test that they are evenly distributed."""

    nsamples = 1000  # don't make this too small
    volfrac = 0.5  # sets inner ellipse size

    for n in range(1, NMAX+1):
        ell = random_ellipsoid(n)  # random ellipsoid
        ell2 = deepcopy(ell)
        ell2.scale_to_vol(volfrac * ell2.vol)  # smaller ellipsoid

        # expected number of points that will fall within inner ellipsoid
        expect = volfrac * nsamples
        sigma = math.sqrt((1. - volfrac) * volfrac * nsamples) # normal approx.

        # sample randomly. For each point, check if point is within
        # main ellipsoid and count the number of points within the
        # inner ellipsoid.
        ninner = 0
        for i in range(nsamples):
            x = ell.sample()
            assert ell.contains(x)
            ninner += ell2.contains(x)

        # check that the number of points in the inner ellipse is what
        # we expect (practically guaranteed to be in range +/- 10 sigma!)
        assert expect - 10.*sigma < ninner < expect + 10.*sigma


def test_bounding_ellipsoid():
    """Test that bounding ellipsoid contains the points"""

    npoints = 100

    for n in range(1, NMAX+1):
        ell_gen = random_ellipsoid(n)  # random elipsoid
        x = ell_gen.samples(npoints)  # points within it
        ell = nestle.bounding_ellipsoid(x)
        for xi in x:
            assert ell.contains(xi)

        print("n={}: true_vol={}  vol={}".format(n, ell_gen.vol, ell.vol))


def test_bounding_ellipsoid_few_points(): 
    """Test that bounding ellipsoid still works when npoints < dim but
    pointvol > 0."""

    for n in range(1, NMAX+1):
        ell_gen = random_ellipsoid(n)
        for npoints in range(1, n):
            x = ell_gen.samples(npoints)

            # check that it works
            ell = nestle.bounding_ellipsoid(x, pointvol=ell_gen.vol/npoints)

            # check that volume is as expected
            assert_allclose(ell.vol, ell_gen.vol)

            # check that points are contained
            for xi in x:
                assert ell.contains(xi)

# TODO test_bounding_ellipsoid()

# -----------------------------------------------------------------------------
# Case tests

# TODO: make this more stringent
def test_two_gaussians():
    """Two gaussians in 2-d.

    Note that this is a terrible test in that it will only pass for some 
    random seeds, so if you change the seed, it may fail.
    """

    # gaussians centered at (1, 1) and (-1, -1)
    mu1 = np.ones(2)
    mu2 = -np.ones(2)

    # Width of 0.1 in each dimension
    sigma = 0.1
    ivar = 1.0/(sigma*sigma)
    sigma1inv = np.diag([ivar, ivar])
    sigma2inv = np.diag([ivar, ivar])

    def logl(x):
        dx1 = x - mu1
        dx2 = x - mu2
        return np.logaddexp(-np.dot(dx1, np.dot(sigma1inv, dx1))/2.0,
                            -np.dot(dx2, np.dot(sigma2inv, dx2))/2.0)

    # Use a flat prior, over [-5, 5] in both dimensions
    def prior(x):
        return 10.0 * x - 5.0

    np.random.seed(0)
    res = nestle.sample(logl, prior, 2, npoints=100)
    print("evidence = {0:6.3f} +/- {1:6.3f}".format(res.logz, res.logzerr))

    #(Approximate) analytic evidence for two identical Gaussian blobs,
    # over a uniform prior [-5:5][-5:5] with density 1/100 in this domain:
    analytic_logz = np.log(2.0 * 2.0*np.pi*sigma*sigma / 100.)
    print("analytic = {0:6.3f}".format(analytic_logz))

    # calculate evidence on fine grid.
    dx = 0.1
    xv = np.arange(-5.0 + dx/2., 5., dx)
    yv = np.arange(-5.0 + dx/2., 5., dx)
    grid_logz = -1.e300
    for x in xv:
        for y in yv:
            grid_logz = np.logaddexp(grid_logz, logl(np.array([x, y])))
    grid_logz += np.log(dx * dx / 100.)  # adjust for point density
    print("grid_logz =", grid_logz)

    assert abs(res.logz - analytic_logz) < 2.0 * res.logzerr
    assert abs(res.logz - grid_logz) < 2.0 * res.logzerr

if __name__ == "__main__":
    test_two_gaussian_nest()
