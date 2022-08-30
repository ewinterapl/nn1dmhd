"""Problem definition file for a simple 1-D MHD problem.

This problem definition file describes an electron plasma wave, using
a single equation for the density perturbation n1. This is possible
because in the ideal 1-D MHD case, the x-velocity perturbation v1x,
and the x-component of the electric field (E1x) are both functions of
the density perturbation n1.

This version of the problem contains 2 frequency components, which should
exhibit dispersion as the waves propagate.

The functions in this module are defined using a combination of Numpy and
TensorFlow operations, so they can be used efficiently by the TensorFlow
code.

NOTE: In all code, below, the following indices are assigned to physical
variables (all are perturbations to initial values):

0: n1    # electron number density perturbation

These equations are derived from the ideal MHD equations developed in
Russel et al, applying the assumptions used for electron plasma waves
(see Greenwald notes).

Author
------
Eric Winter (eric.winter62@gmail.com)

"""


import numpy as np
import tensorflow as tf

import nn1dmhd.plasma as plasma


# Names of independent variables.
independent_variable_names = ["x", "t"]

# Number of independent variables.
n_dim = len(independent_variable_names)

# Names of dependent variables.
variable_names = ["n1"]

# Number of dependent variables.
n_var = len(variable_names)

# Normalized physical constants.
kb = 1.0     # Boltzmann constant
me = 1.0     # Electron mass
e = 1.0      # Electron charge
eps0 = 1.0   # Permittivity of free space
gamma = 3.0  # Adiabatic index.

# Define the problem domain.
x0 = 0.0
x1 = 1.0
t0 = 0.0
t1 = 1.0

# Ambient temperature (normalized to unit physical constants).
T = 1.0

# Wavelength and wavenumber of initial density perturbations.
wavelengths = np.array([1.0, 2.0])
kx = 2*np.pi/wavelengths
nc = len(kx)

# Ambient density and density perturbation amplitude at t = 0, for all x.
n0 = 1.0
n10 = np.array([0.1, 0.1])

# Ambient pressure at start.
P0 = n0*kb*T


# Compute the electron plasma angular frequency.
wp = plasma.electron_plasma_angular_frequency(n0, normalize=True)

# Compute the electron plasma wave angular frequency.                           
w = plasma.electron_plasma_wave_angular_frequency(n0, T, kx, normalize=True)

# Compute the electron thermal speed.
vth = plasma.electron_thermal_speed(T, normalize=True)

# Compute the wave phase speed.
vphase = plasma.electron_plasma_wave_phase_speed(n0, T, kx, normalize=True)


def create_training_data(nx:int, nt:int):
    """Create the training data.

    Create and return a set of training data of points evenly spaced in x and
    t. Flatten the data to a list of pairs of points. Also return copies
    of the data containing only internal points, and only boundary points.

    Parameters
    ----------
    nx, nt : int
        Number of points in x- and t- dimensions.

    Returns
    -------
    xt : np.ndarray, shape (nx*nt, 2)
        Array of all [x, t] points.
    xt_in : np.ndarray, shape ((nx - 1)*(nt - 2)), 2)
        Array of all [x, t] points within boundary.
    xt_bc : np.ndarray, shape (nx + 2*(nt - 1), 2)
        Array of all [x, t] points at boundary.
    """
    # Create the array of all training points (x, t), looping over t then x.
    x = np.linspace(x0, x1, nx)
    t = np.linspace(t0, t1, nt)
    X = np.repeat(x, nt)
    T = np.tile(t, nx)
    xt = np.vstack([X, T]).T

    # Now split the training data into two groups - inside the BC, and on the
    # BC.
    # Initialize the mask to keep everything.
    mask = np.ones(len(xt), dtype=bool)
    # Mask off the points at x = 0.
    mask[:nt] = False
    # Mask off the points at x = 1.
    # mask[-nt:] = False
    # Mask off the points at t = 0.
    mask[::nt] = False

    # Extract the internal points.
    xt_in = xt[mask]

    # Invert the mask and extract the boundary points.
    mask = np.logical_not(mask)
    xt_bc = xt[mask]
    return xt, xt_in, xt_bc


def compute_boundary_conditions(xt:np.ndarray):
    """Compute the boundary conditions.

    Parameters
    ----------
    xt : np.ndarray of float
        Values of (x, t) on the boundaries, shape (n_bc, 2)

    Returns
    -------
    bc : np.ndarray of float, shape (n_bc, n_var)
        Values of each dependent variable on boundary.
    """
    w = plasma.electron_plasma_wave_angular_frequency(n0, T, kx, normalize=True)
    n = len(xt)
    bc = np.empty((n, n_var))
    for (i, (x, t)) in enumerate(xt):
        if np.isclose(x, x0):
            # Periodic perturbation at x = x0 = 0.
            bc[i, :] = [
                n10[0]*np.sin(-w[0]*t) + n10[1]*np.sin(-w[1]*t),
            ]
        # elif np.isclose(x, x1):
        #     # Periodic perturbation at x = x1, same as at x = x0.
        #     bc[i, :] = [
        #         n10[0]*np.sin(-w[0]*t) + n10[1]*np.sin(-w[1]*t),
        #     ]
        elif np.isclose(t, t0):
            bc[i, :] = [
                n10[0]*np.sin(kx[0]*x) + n10[1]*np.sin(kx[1]*x),
            ]
        else:
            raise ValueError
    return bc


# Define the differential equations using TensorFlow operations.

# @tf.function
def pde_n1(xt, Y1, del_Y1):
    """Differential equation for n1.

    Evaluate the differential equation for n1 (number density perturbation).

    Parameters
    ----------
    xt : tf.Variable, shape (n, 2)
        Values of (x, t) at each training point.
    Y1 : list of n_var tf.Tensor, each shape (n, 1)
        Perturbations of dependent variables at each training point.
    del_Y1 : list of n_var tf.Tensor, each shape (n, 2)
        Values of gradients of Y1 wrt (x, t) at each training point.

    Returns
    -------
    G : tf.Tensor, shape(n, 1)
        Value of differential equation at each training point.
    """
    n = xt.shape[0]
    # Each of these Tensors is shape (n, 1).
    # x = tf.reshape(xt[:, 0], (n, 1))
    # t = tf.reshape(xt[:, 1], (n, 1))
    # (n1,) = Y1
    # (del_n1,) = del_Y1
    (del_n1,) = del_Y1
    dn1_dx = tf.reshape(del_n1[:, 0], (n, 1))
    dn1_dt = tf.reshape(del_n1[:, 1], (n, 1))

    # G is a Tensor of shape (n, 1).
    G = dn1_dt + w/kx*dn1_dx
    return G


# Make a list of all of the differential equations.
differential_equations = [
    pde_n1,
]
