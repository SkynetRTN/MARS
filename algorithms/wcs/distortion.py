"""Conservative invertibility validation for solver-produced SIP maps.

For one fixed matrix K, a positive-definite symmetric part of K J(x)
throughout the detector makes K F strictly monotone. Integrating its Jacobian
along any line segment proves that distinct pixels cannot have the same image.
Outward-rounded polynomial intervals certify whole boxes, rather than just
sampling a Jacobian at a few pixels. Uncertifiable maps are rejected.
"""

import math

import numpy as np


def _add(a, b):
    return math.nextafter(a[0]+b[0], -math.inf), math.nextafter(a[1]+b[1], math.inf)


def _multiply(a, b):
    products = [x*y for x in a for y in b]
    return math.nextafter(min(products), -math.inf), math.nextafter(max(products), math.inf)


def _power(interval, exponent):
    if exponent == 0:
        return 1., 1.
    endpoints = []
    for endpoint in interval:
        value = (endpoint, endpoint)
        for _ in range(exponent-1):
            value = _multiply(value, (endpoint, endpoint))
        endpoints.append(value)
    lower = min(value[0] for value in endpoints)
    if exponent % 2 == 0 and interval[0] <= 0 <= interval[1]:
        lower = 0.
    return lower, max(value[1] for value in endpoints)


def _bounds(terms, x, y):
    result = (0., 0.)
    for coefficient, i, j in terms:
        term = _multiply(_power(x, i), _power(y, j))
        result = _add(result, _multiply(coefficient, term))
    if not all(math.isfinite(value) for value in result):
        raise ValueError("SIP derivative bounds are nonfinite")
    return result


def validate_distortion(wcs, width: int, height: int) -> None:
    """Certify the forward detector map, or refuse an unsupported/uncertain map."""
    if any(getattr(wcs, name) is not None for name in ("cpdis1", "cpdis2", "det2im1", "det2im2")):
        raise ValueError("lookup-table distortion invertibility is not supported")
    sip = wcs.sip
    if sip is None:
        return
    if not np.array_equal(sip.crpix, wcs.wcs.crpix):
        raise ValueError("SIP and celestial reference pixels disagree")
    derivatives = []
    for row, coefficients in enumerate((sip.a, sip.b)):
        if not np.isfinite(coefficients).all():
            raise ValueError("SIP coefficients are nonfinite")
        order = coefficients.shape[0]-1
        if any(coefficients[i, j] != 0 for i, j in np.ndindex(coefficients.shape) if i+j > order):
            raise ValueError("SIP coefficients exceed their declared total order")
        for axis in range(2):
            terms = [((1., 1.), 0, 0)] if row == axis else []
            for i, j in zip(*np.nonzero(coefficients)):
                exponent = int((i, j)[axis])
                if exponent:
                    coefficient = float(coefficients[i, j])
                    # Differentiation itself rounds; enclose that product too.
                    factor = _multiply((coefficient, coefficient), (exponent, exponent))
                    terms.append((factor, int(i)-(axis == 0), int(j)-(axis == 1)))
            derivatives.append(terms)
    x = (math.nextafter(.5-float(sip.crpix[0]), -math.inf),
         math.nextafter(width+.5-float(sip.crpix[0]), math.inf))
    y = (math.nextafter(.5-float(sip.crpix[1]), -math.inf),
         math.nextafter(height+.5-float(sip.crpix[1]), math.inf))
    ranges = [_bounds(terms, x, y) for terms in derivatives]
    midpoint = np.array([lo/2+hi/2 for lo, hi in ranges]).reshape(2, 2)
    try:
        preconditioner = np.linalg.inv(midpoint)
    except np.linalg.LinAlgError as exc:
        raise ValueError("SIP map cannot be certified invertible") from exc
    if not np.isfinite(preconditioner).all():
        raise ValueError("SIP map cannot be certified invertible")

    pending = [(x, y, 0)]
    visited = 0
    while pending:
        x_box, y_box, depth = pending.pop()
        visited += 1
        jacobian = [_bounds(terms, x_box, y_box) for terms in derivatives]
        transformed = []
        for row in range(2):
            for column in range(2):
                interval = (0., 0.)
                for k in range(2):
                    scale = float(preconditioner[row, k])
                    interval = _add(interval, _multiply((scale, scale), jacobian[2*k+column]))
                if not all(math.isfinite(value) for value in interval):
                    raise ValueError("SIP invertibility bounds are nonfinite")
                transformed.append(interval)
        # Sylvester's criterion, with lower diagonal and upper off-diagonal
        # bounds, certifies every symmetric Jacobian in this entire box.
        first, second = transformed[0][0], transformed[3][0]
        off_diagonal = _multiply((.5, .5), _add(transformed[1], transformed[2]))
        off_bound = max(abs(value) for value in off_diagonal)
        determinant_lower_product = _multiply((first, first), (second, second))[0]
        off_square_upper = _power((off_bound, off_bound), 2)[1]
        certified = first > 0 and second > 0 and determinant_lower_product > off_square_upper
        if certified:
            continue
        if depth >= 12 or visited >= 4096:
            raise ValueError("SIP map cannot be certified invertible over the detector")
        # One fixed preconditioner is used across every box; separate local
        # invertibility checks would not establish global injectivity.
        axis = int(y_box[1]-y_box[0] > x_box[1]-x_box[0])
        interval = y_box if axis else x_box
        middle = interval[0]/2+interval[1]/2
        if not interval[0] < middle < interval[1]:
            raise ValueError("SIP invertibility bounds cannot be refined")
        for half in ((interval[0], middle), (middle, interval[1])):
            pending.append((x_box if axis else half, half if axis else y_box, depth+1))
