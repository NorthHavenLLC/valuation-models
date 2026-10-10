"""Shared grid validation and interpolation for both chart engines."""

import numpy as np


def _surface_data(xx, yy, zz):
    """Validate the rectilinear model grid; keep undefined scenarios as gaps."""
    xx, yy, zz = (np.asarray(a, dtype=float) for a in (xx, yy, zz))
    if xx.ndim != 2 or xx.shape != yy.shape or xx.shape != zz.shape or min(xx.shape) < 2:
        raise ValueError("Surface inputs must be matching 2D grids with at least two points per axis")
    if not (np.isfinite(xx).all() and np.isfinite(yy).all()):
        raise ValueError("Surface coordinates must be finite")
    if not (np.allclose(xx, xx[0, :][None, :]) and np.allclose(yy, yy[:, 0][:, None])):
        raise ValueError("Surface inputs must form a rectilinear meshgrid")
    if not (np.all(np.diff(xx[0]) > 0) and np.all(np.diff(yy[:, 0]) > 0)):
        raise ValueError("Surface coordinates must be strictly increasing")
    return xx, yy, np.where(np.isfinite(zz), zz, np.nan)


def _surface_slice(coordinates, values, at):
    """Linear interpolation between adjacent model rows, without filling gaps."""
    if at < coordinates[0] or at > coordinates[-1]:
        return np.full(values.shape[1], np.nan)
    high = int(np.searchsorted(coordinates, at))
    if high < len(coordinates) and np.isclose(coordinates[high], at, rtol=0, atol=1e-12):
        return values[high].copy()
    low = max(0, high - 1)
    weight = (at - coordinates[low]) / (coordinates[high] - coordinates[low])
    return values[low] * (1 - weight) + values[high] * weight


def surface_diagnostics(xx, yy, zz, reference=None):
    """Finite-difference slopes in displayed axis units; gaps remain undefined.

    Grid coverage is a count of sampled model scenarios, not a probability.
    """
    x, y, z = _surface_data(xx, yy, zz)
    dy, dx = np.gradient(z, y[:, 0], x[0], edge_order=1)
    valid = np.isfinite(z)
    dx[~valid] = np.nan
    dy[~valid] = np.nan
    delta = z - reference if reference is not None and np.isfinite(reference) else np.full_like(z, np.nan)
    return np.stack([delta, dx, dy], axis=-1)
