"""Reference-magnitude resolution: image FILTER -> catalog band / colour expression.

EXTRACTED FROM: skynet/packages/py/skynet-db/skynet_db/runners/utils.py
lines 605-799 (``_SAFE_NAMES``, ``_ALLOWED_TOKENS``, ``_get_catalog_filter_lookup``,
``_safe_eval_expr``, ``_resolve_filter_lookup_candidate``,
``_ref_mag_filter_token_candidates``, ``resolve_ref_mag_for_filter``).
PHOT-15 adds first-party bounded arithmetic evaluation and literal band matching;
accepted transforms and the resolution/propagation order remain unchanged.

The legacy-Afterglow-parity notes in the docstrings and the gated
``allow_preferred_band_fallback`` behaviour are preserved exactly — they are the
documented numeric-parity contract with the previous system.
"""
from __future__ import annotations

import ast
import math
import operator
import re

from algorithms.catalogs import CATALOG_OPTIONS
from algorithms.catalogs.filters import filter_token_candidates
from .schemas import Mag  # noqa: F401  (referenced by the type annotation below)

__all__ = ["resolve_ref_mag_for_filter"]


_SAFE_NAMES = {k: getattr(math, k) for k in ("sqrt", "log10")}
_ALLOWED_TOKENS = re.compile(r"[A-Za-z0-9_+\-*/().\s]+")

# First-party expression acceptance limits, not photometric formula changes.
MAX_EXPRESSION_LENGTH = 2_048
MAX_EXPRESSION_NODES = 256
MAX_EXPRESSION_DEPTH = 32
MAX_EXPRESSION_EXPONENT = 16
MAX_EXPRESSION_INTEGER_BITS = 1_024
MAX_EXPRESSION_BANDS = 64
MAX_EXPRESSION_BAND_NAME = 128
MAX_LOOKUP_HOPS = 32
_BINARY_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _numeric(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expressions require real numeric values.")
    if isinstance(value, int):
        if value.bit_length() > MAX_EXPRESSION_INTEGER_BITS:
            raise ValueError("Expression integer exceeds the bit limit.")
    elif not math.isfinite(value):
        raise ValueError("Expression value is not finite.")
    return value


def _literal_exponent(node: ast.AST) -> int | float:
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        node = node.operand
    if not isinstance(node, ast.Constant):
        raise ValueError("Power exponents must be numeric literals, not expressions.")
    value = sign * _numeric(node.value)
    if abs(value) > MAX_EXPRESSION_EXPONENT:
        raise ValueError("Power exponent exceeds the expression limit.")
    return value


def _validate_expression(tree: ast.AST, namespace: dict) -> None:
    allowed = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp,
               ast.UnaryOp, ast.Call, *_BINARY_OPERATORS, *_UNARY_OPERATORS)
    pending = [(tree, 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_EXPRESSION_NODES or depth > MAX_EXPRESSION_DEPTH:
            raise ValueError("Expression exceeds the node/depth limit.")
        if not isinstance(node, allowed):
            raise ValueError("Expression syntax is not numeric arithmetic.")
        if isinstance(node, ast.Constant):
            _numeric(node.value)
        elif isinstance(node, ast.Name) and node.id not in namespace:
            raise ValueError("Expression names an unavailable band.")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            _literal_exponent(node.right)
        elif isinstance(node, ast.Call):
            if (not isinstance(node.func, ast.Name)
                    or node.func.id not in _SAFE_NAMES
                    or namespace.get(node.func.id) is not _SAFE_NAMES[node.func.id]
                    or len(node.args) != 1 or node.keywords):
                raise ValueError("Only unshadowed sqrt/log10 single-argument calls are supported.")
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))


def _evaluate_expression(node: ast.AST, namespace: dict) -> int | float:
    """Evaluate only the prevalidated bounded tree; never compile or use eval."""
    if isinstance(node, ast.Expression):
        return _evaluate_expression(node.body, namespace)
    if isinstance(node, ast.Constant):
        value = node.value
    elif isinstance(node, ast.Name):
        value = namespace[node.id]
    elif isinstance(node, ast.UnaryOp):
        value = _UNARY_OPERATORS[type(node.op)](_evaluate_expression(node.operand, namespace))
    elif isinstance(node, ast.BinOp):
        left = _evaluate_expression(node.left, namespace)
        right = _evaluate_expression(node.right, namespace)
        value = _BINARY_OPERATORS[type(node.op)](left, right)
    elif isinstance(node, ast.Call):
        value = _SAFE_NAMES[node.func.id](_evaluate_expression(node.args[0], namespace))
    else:
        raise ValueError("Unsupported expression node.")
    return _numeric(value)


def _get_catalog_filter_lookup(catalog_name: str | None) -> dict[str, str]:
    if not catalog_name:
        return {}

    catalog = CATALOG_OPTIONS.get(catalog_name)
    if catalog is None:
        return {}
    return catalog.filter_lookup

def _safe_eval_expr(expr: str, bands: dict[str, float]) -> float | None:
    """Return a finite bounded arithmetic result or the legacy unresolved None."""
    if (not expr or len(expr) > MAX_EXPRESSION_LENGTH
            or len(bands) > MAX_EXPRESSION_BANDS or not _ALLOWED_TOKENS.fullmatch(expr)):
        return None
    try:
        # Parentheses disappear in the AST: bound nesting before parsing too.
        depth = 0
        for char in expr:
            if char == "(":
                depth += 1
                if depth > MAX_EXPRESSION_DEPTH:
                    return None
            elif char == ")":
                depth -= 1
        ns = dict(_SAFE_NAMES)
        identifiers: set[str] = set()
        expr2 = expr
        for k, v in bands.items():
            if not isinstance(k, str) or not k or len(k) > MAX_EXPRESSION_BAND_NAME:
                return None
            kid = re.sub(r"[^A-Za-z0-9_]", "_", k)
            if kid in identifiers:
                return None  # Two bands must not silently share a rewritten name.
            identifiers.add(kid)
            ns[kid] = _numeric(float(v))
            expr2 = re.sub(rf"\b{re.escape(k)}\b", kid, expr2)
        tree = ast.parse(expr2.strip(), mode="eval")
        _validate_expression(tree, ns)
        return float(_evaluate_expression(tree, ns))
    except (ValueError, TypeError, ArithmeticError, SyntaxError, RecursionError):
        return None


def _resolve_filter_lookup_candidate(
    candidate: str,
    band_vals: dict[str, tuple[float | None, float | None]],
    lookup: dict[str, str],
    *,
    propagate_error: bool,
) -> tuple[float | None, float | None]:
    """Resolve a lookup target, following aliases such as SII -> rprime."""
    if len(band_vals) > MAX_EXPRESSION_BANDS:
        return None, None
    seen: set[str] = set()
    current = candidate
    while current and current not in seen and len(seen) < MAX_LOOKUP_HOPS:
        seen.add(current)

        v, e = band_vals.get(current, (None, None))
        if v is not None:
            return float(v), (float(e) if e is not None else None)

        bands = {k: v for k, (v, _) in band_vals.items() if v is not None}
        val = _safe_eval_expr(current, bands)
        if val is not None:
            if not propagate_error:
                return float(val), None
            eps = 1e-7
            err2 = 0.0
            for k, (v, e) in band_vals.items():
                if v is None or e in (None, 0):
                    continue
                bands[k] = float(v) + eps
                v2 = _safe_eval_expr(current, bands)
                bands[k] = float(v)  # restore
                if v2 is not None:
                    dmdk = (v2 - val) / eps
                    err2 += (dmdk * float(e)) ** 2
            return float(val), (err2 ** 0.5 if err2 > 0 else None)

        current = lookup.get(current)

    return None, None


def _ref_mag_filter_token_candidates(image_filter: str) -> list[str]:
    """Filter-name variants to try for a *direct* catalog-band match.

    Mirrors ``query.selection._filter_token_candidates`` so reference-magnitude
    resolution and the filter-aware catalog preselection agree on which filters
    a catalog can satisfy via a direct band (e.g. both treat APASS as able to
    serve a ``B`` image from its ``Bmag`` column). Preserves the original
    token's casing first so meaningful tokens like ``g'`` / ``Halpha`` are not
    rewritten before the lookup-based steps get a chance to run.
    """
    return [token for token in filter_token_candidates(image_filter) if token]


def resolve_ref_mag_for_filter(
    *,
    image_filter: str | None,
    catalog_name: str | None,
    cs_mags: dict[str, "Mag"] | dict[str, dict[str, float]],
    propagate_error: bool = True,
    custom_filter_lookup: dict[str, dict[str, str]] | None = None,
    allow_preferred_band_fallback: bool = True,
) -> tuple[float | None, float | None]:
    """
    Resolve the catalog reference magnitude for the given FITS FILTER using
    per-catalog mapping rules and (optionally) propagate error for expressions.

    Resolution order mirrors legacy Afterglow field calibration
    (``field_cal_job.py``):

      1. Direct catalog band whose key matches the image filter name
         (legacy: ``catalog_source.mags[flt]``). This takes precedence over the
         per-catalog ``filter_lookup`` so that a ``B`` image calibrates against
         the catalog ``B`` magnitude rather than an unrelated band.
      2. A ``filter_lookup`` entry (or ``"*"`` wildcard) that resolves to a
         direct band or another lookup alias.
      3. A ``filter_lookup`` entry that is a colour-mapping expression.

    ``allow_preferred_band_fallback`` controls a *non-legacy* Skynet behavior:
    when ``True`` (default), an unresolved filter falls back to a preferred band
    (``V``, ``r'``, ``g'``, ``B``, ``i'``, then any available band). Legacy
    Afterglow has no such fallback — it skips the source. Strict legacy-parity
    callers (field calibration parity mode, the Afterglow ZP diagnostic) pass
    ``False`` so an unresolved filter returns ``(None, None)`` instead of
    silently substituting a wrong reference band.
    """
    if not cs_mags or len(cs_mags) > MAX_EXPRESSION_BANDS:
        return None, None

    # flatten to {band: (value, error)}
    band_vals: dict[str, tuple[float | None, float | None]] = {}
    for k, v in cs_mags.items():
        if hasattr(v, "value"):
            band_vals[k] = (getattr(v, "value", None), getattr(v, "error", None))
        elif isinstance(v, dict):
            band_vals[k] = (v.get("value"), v.get("error"))
        else:
            try:
                band_vals[k] = (float(v), None)
            except Exception:
                band_vals[k] = (None, None)

    f = (image_filter or "").strip()

    # 1. Direct catalog band matching the image filter name (legacy parity).
    if f:
        for token in _ref_mag_filter_token_candidates(f):
            v, e = band_vals.get(token, (None, None))
            if v is not None:
                return float(v), (float(e) if e is not None else None)

    lookup = _get_catalog_filter_lookup(catalog_name)
    if custom_filter_lookup and catalog_name:
        lookup = {**lookup, **custom_filter_lookup.get(catalog_name, {})}

    # 2-3. Explicit filter lookup resolving to a direct band, another lookup
    #      alias, or a colour-mapping expression.
    explicit_lookup_seen = False
    for token in _ref_mag_filter_token_candidates(f):
        candidate = lookup.get(token)
        if not candidate:
            continue
        explicit_lookup_seen = True
        v, e = _resolve_filter_lookup_candidate(
            candidate,
            band_vals,
            lookup,
            propagate_error=propagate_error,
        )
        if v is not None:
            return v, e
    if explicit_lookup_seen:
        return None, None

    # Wildcard default like legacy; only use it when no explicit token matched.
    candidate = lookup.get("*")
    if candidate:
        v, e = _resolve_filter_lookup_candidate(
            candidate,
            band_vals,
            lookup,
            propagate_error=propagate_error,
        )
        if v is not None:
            return v, e

    # CAT-01: without an explicit transform, SkyMapper has no Johnson V.
    # Do not reintroduce the band substitution through the permissive fallback.
    if catalog_name == "SkyMapper" and f == "V":
        return None, None

    # 4. Preferred-band fallback (NON-legacy; gated). Legacy Afterglow skips a
    #    source whose filter resolves to no direct band or mapping expression.
    if allow_preferred_band_fallback:
        for pref in ("V", "rprime", "gprime", "B", "iprime"):
            v, e = band_vals.get(pref, (None, None))
            if v is not None:
                return float(v), (float(e) if e is not None else None)
        for k, (v, e) in band_vals.items():
            if v is not None:
                return float(v), (float(e) if e is not None else None)
    return None, None
