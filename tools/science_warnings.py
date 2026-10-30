"""Translate retained numerical disclosures at public tool boundaries."""

from contextlib import contextmanager

from algorithms.diagnostics import collect_numerical_notices
from tools.models import ToolWarning


@contextmanager
def capture_numerical_warnings(warnings: list[ToolWarning]):
    """Append notices before the caller constructs a success or failure result."""
    with collect_numerical_notices() as notices:
        try:
            yield
        finally:
            for notice in notices:
                match notice.code:
                    case "nonpositive_aperture_flux":
                        warning = ToolWarning(code="nonpositive_aperture_flux", message=notice.message)
                    case "empty_background_annulus":
                        warning = ToolWarning(code="empty_background_annulus", message=notice.message)
                    case "isophotal_origin_approximation":
                        warning = ToolWarning(code="isophotal_origin_approximation", message=notice.message)
                    case "aperture_correction_crowding":
                        warning = ToolWarning(code="aperture_correction_crowding", message=notice.message)
                    case "saturation_count_unreliable":
                        warning = ToolWarning(code="saturation_count_unreliable", message=notice.message)
                    case "limiting_magnitude_unvalidated":
                        warning = ToolWarning(code="limiting_magnitude_unvalidated", message=notice.message)
                    case "limiting_magnitude_unidentifiable":
                        warning = ToolWarning(code="limiting_magnitude_unidentifiable", message=notice.message)
                    case "magnitude_error_snr_cut":
                        warning = ToolWarning(code="magnitude_error_snr_cut", message=notice.message)
                    case "ra_seam_matching_approximation":
                        warning = ToolWarning(code="ra_seam_matching_approximation", message=notice.message)
                    case _:
                        raise ValueError(f"Unknown numerical notice: {notice.code}")
                if warning not in warnings:
                    warnings.append(warning)
