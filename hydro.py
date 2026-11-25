"""Daily event-based phi index and unit-hydrograph calculations.

All rain/runoff depths are mm per daily interval, flow is m3/s,
catchment area is km2. Educational event-scale model, not continuous hydrology.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import nnls, brentq

SECONDS_PER_DAY = 86400.0


def flow_to_mm_day(q_cms, area_km2):
    if area_km2 <= 0:
        raise ValueError('Area must be positive.')
    return np.asarray(q_cms, dtype=float) * SECONDS_PER_DAY / (area_km2 * 1000.0)


def depth_to_flow(depth_mm_day, area_km2):
    return np.asarray(depth_mm_day, dtype=float) * area_km2 * 1000.0 / SECONDS_PER_DAY


def phi_index(p_mm, direct_runoff_mm):
    """Solve sum(max(P-phi,0)) == observed runoff depth in mm."""
    p = np.asarray(p_mm, dtype=float)
    if not len(p) or not np.all(np.isfinite(p)) or np.any(p < 0):
        raise ValueError('Rainfall must be finite, nonnegative, and nonempty.')
    r = float(direct_runoff_mm)
    if not np.isfinite(r) or r < 0:
        raise ValueError('Direct runoff must be finite and nonnegative.')
    total = float(p.sum())
    if r > total + 1e-6:
        raise ValueError(f'Direct runoff depth ({r:.2f} mm) exceeds rainfall ({total:.2f} mm). Check the event, area, and baseflow.')
    if r <= 1e-9:
        return float(p.max())  # not uniquely identifiable; app warns separately
    if abs(r - total) <= 1e-9:
        return 0.0
    return float(brentq(lambda x: np.maximum(p - x, 0).sum() - r, 0, p.max()))


def excess_rain(p_mm, phi_mm_day):
    return np.maximum(np.asarray(p_mm, dtype=float) - float(phi_mm_day), 0)


def baseflow_series(q_cms, mode='Straight line (first to last day)'):
    q = np.asarray(q_cms, dtype=float)
    if mode == 'Constant (first day)':
        base = np.full(len(q), q[0])
    elif mode == 'Straight line (first to last day)':
        base = np.linspace(q[0], q[-1], len(q))
    else:
        raise ValueError('Unknown baseflow mode')
    # Bound by observed streamflow to avoid creating negative direct runoff.
    return np.minimum(base, q)


def conv_matrix(rain_excess, n_ordinates):
    e = np.asarray(rain_excess, dtype=float)
    a = np.zeros((len(e), n_ordinates))
    for j in range(n_ordinates):
        a[j:, j] = e[:len(e) - j]
    return a


@dataclass
class Calibration:
    phi_mm_day: float
    baseflow_cms: np.ndarray
    direct_cms: np.ndarray
    excess_mm: np.ndarray
    unit_ordinates: np.ndarray  # m3/s per mm effective rainfall
    modeled_direct_cms: np.ndarray
    r2: float
    nse: float
    observed_runoff_mm: float
    excess_total_mm: float
    unit_volume_ratio: float
    event_rain_mm: float


def calibrate(p_mm, q_cms, area_km2, n_ordinates=8,
              baseflow_mode='Straight line (first to last day)',
              regularization=0.01):
    p = np.asarray(p_mm, dtype=float)
    q = np.asarray(q_cms, dtype=float)
    if len(p) != len(q) or len(p) < 5:
        raise ValueError('Storm window needs at least five days with matching rain and flow.')
    if not np.all(np.isfinite(p)) or not np.all(np.isfinite(q)) or np.any(p < 0) or np.any(q < 0):
        raise ValueError('Precipitation and discharge must be finite and nonnegative.')
    if area_km2 <= 0:
        raise ValueError('Area must be greater than zero.')
    if not 2 <= n_ordinates <= len(p):
        raise ValueError('Unit hydrograph length must be between 2 and the number of event days.')
    base = baseflow_series(q, baseflow_mode)
    direct = np.maximum(q - base, 0)
    runoff_mm = float(flow_to_mm_day(direct, area_km2).sum())
    if runoff_mm < 0.01:
        raise ValueError('No meaningful direct runoff in this event; select another storm or baseflow method.')
    phi = phi_index(p, runoff_mm)
    excess = excess_rain(p, phi)
    if np.count_nonzero(excess) == 0:
        raise ValueError('No effective rainfall was identified.')
    a = conv_matrix(excess, n_ordinates)
    # Impose smooth ordinates with a first-difference penalty scaled to the
    # hydrograph's own normal equations. Nonnegative solution is physical.
    d = np.diff(np.eye(n_ordinates), axis=0)
    scale = max(float(np.linalg.norm(a, ord='fro')**2 / n_ordinates), 1e-10)
    augmented = np.vstack((a, np.sqrt(regularization * scale) * d))
    rhs = np.r_[direct, np.zeros(n_ordinates - 1)]
    unit, _ = nnls(augmented, rhs)
    # A 1-mm unit hydrograph must route 1 mm over the entire catchment.
    # Preserve mass balance and report loss of fit when normalizing.
    expected_sum = float(depth_to_flow(1.0, area_km2))
    actual_sum = float(unit.sum())
    if actual_sum <= 0:
        raise ValueError('Unable to estimate nonzero UH ordinates for this event.')
    ratio = actual_sum / expected_sum
    unit = unit * (expected_sum / actual_sum)
    modeled = a @ unit
    residual = float(np.sum((direct - modeled)**2))
    denom = float(np.sum((direct - direct.mean())**2))
    nse = 1.0 - residual / denom if denom > 1e-12 else float('nan')
    corr = np.corrcoef(direct, modeled)[0, 1] if np.std(direct) > 0 and np.std(modeled) > 0 else float('nan')
    r2 = float(corr**2) if np.isfinite(corr) else float('nan')
    return Calibration(phi, base, direct, excess, unit, modeled, r2, nse,
                       runoff_mm, float(excess.sum()), ratio, float(p.sum()))


def simulate(p_mm, phi_mm_day, unit_ordinates, baseline_cms=0.0):
    p = np.asarray(p_mm, dtype=float)
    if len(p) == 0 or not np.all(np.isfinite(p)) or np.any(p < 0):
        raise ValueError('Scenario precipitation must contain finite nonnegative values.')
    if baseline_cms < 0:
        raise ValueError('Scenario baseflow must be nonnegative.')
    e = excess_rain(p, phi_mm_day)
    direct = np.convolve(e, np.asarray(unit_ordinates, dtype=float), mode='full')
    return e, direct, direct + baseline_cms
