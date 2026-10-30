"""
MARS: Landolt catalog of UBVRI photometric standards
accessed via VizieR
"""

from typing import List as TList, Union

from numpy import hypot, sqrt
from astropy.table import Table

from .schemas import CatalogSource, Mag
# EXTRACTED: was `from .vizier_catalogs import VizierCatalog`. In MARS the
# VizieR backend lives in ``query/vizier.py`` and is mixed onto this class at
# import time by ``query/binding.py``, so this module stays declaration-only and
# carries no network dependency.
from .catalog import Catalog


__all__ = ['LandoltCatalog']


def _err(mag) -> float:
    """A band's error, 0 when unset or the band is absent."""
    return (getattr(mag, 'error', None) or 0) if mag is not None else 0


class LandoltCatalog(Catalog):
    """
    Landolt/VizieR catalog plugin
    """
    name = 'Landolt'
    display_name = 'Landolt Catalog of UBVRI Photometric Standards'
    num_sources = 526
    vizier_catalog = 'II/183A'
    mags = {
        'U': [], 'B': [], 'V': ['Vmag', 'e_Vmag'], 'R': [], 'I': [],
        'B_V': ['B-V', 'e_B-V'], 'U_B': ['U-B', 'e_U-B'],
        'V_R': ['V-R', 'e_V-R'], 'R_I': ['R-I', 'e_R-I'],
        'V_I': ['V-I', 'e_V-I'],
    }
    col_mapping = {
        'id': 'Star',
        'ra_hours': 'int(RAJ2000.split()[0]) + int(RAJ2000.split()[1])/60 + '
        'float(RAJ2000.split()[2])/3600',
        'dec_degs': '(abs(int(DEJ2000.split()[0])) + '
        'int(DEJ2000.split()[1])/60 + float(DEJ2000.split()[2])/3600)*'
        '(1 - 2*(DEJ2000.strip().startswith("-")))',
    }

    # Photometric transform, preserved verbatim. ``super().table_to_sources``
    # resolves to the bound VizieR row mapper in ``query/vizier.py`` (see
    # ``query/binding.py`` for the MRO), which returns the raw colour indices
    # this method then converts to UBVRI.
    #
    # PRESERVED BUG: the error on U is computed from ``V_R`` where the colour
    # algebra calls for ``U_B``. That is upstream's expression, kept as written
    # -- U magnitudes are correct, only their reported uncertainty is wrong.
    def table_to_sources(self, table: Union[list, Table]) \
            -> TList[CatalogSource]:
        """
        Return a list of :class:`CatalogSource` objects from an Astropy table

        Converts color indices to magnitudes.

        :param table: table of sources returned by astroquery

        :return: list of catalog objects
        """
        sources = super().table_to_sources(table)

        for source in sources:
            mags = source.mags
            # EXTRACTED: upstream read errors with ``getattr(mag, 'error', 0)``,
            # which assumed an unset error attribute was absent. MARS's ``Mag``
            # always has ``error``, defaulting to None, so any row with a zero or
            # unrecorded catalog error raised ``None ** 2`` (M3). ``_err`` reads
            # an unset error as 0, the upstream intent. An absent colour leaves its dependent bands underived. M2 retains
            # finite zero colours (CAT-23).
            if 'V' not in mags:
                continue
            v, v_err = mags['V'].value, _err(mags['V'])

            if 'B_V' in mags:
                mags['B'] = Mag(value=v + mags['B_V'].value)
                err = hypot(v_err, _err(mags['B_V']))
                if err:
                    mags['B'].error = err

            if 'B' in mags and 'U_B' in mags:
                mags['U'] = Mag(value=mags['B'].value + mags['U_B'].value)
                err = hypot(_err(mags['B']), _err(mags.get('V_R')))
                if err:
                    mags['U'].error = err

            if 'V_R' in mags:
                mags['R'] = Mag(value=v - mags['V_R'].value)
                err = hypot(v_err, _err(mags['V_R']))
                if err:
                    mags['R'].error = err

            if 'R' in mags and 'R_I' in mags and 'V_I' in mags:
                mags['I'] = Mag(
                    value=(mags['R'].value - mags['R_I'].value +
                           v - mags['V_I'].value)/2)
                err = sqrt((_err(mags['R'])**2 +
                            _err(mags['R_I'])**2 +
                            v_err**2 + _err(mags['V_I'])**2)/2)
                if err:
                    mags['I'].error = err

        return sources
