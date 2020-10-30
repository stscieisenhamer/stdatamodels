"""
Various utility functions and data types
"""

import os

import numpy as np
from astropy.io import fits
import asdf

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def gentle_asarray(a, dtype):
    """
    Performs an asarray that doesn't cause a copy if the byteorder is
    different.  It also ignores column name differences -- the
    resulting array will have the column names from the given dtype.
    """
    out_dtype = np.dtype(dtype)
    if isinstance(a, np.ndarray):
        in_dtype = a.dtype
        # Non-table array
        if in_dtype.fields is None and out_dtype.fields is None:
            if np.can_cast(in_dtype, out_dtype, 'equiv'):
                return a
            else:
                return np.asanyarray(a, dtype=out_dtype)
        elif in_dtype.fields is not None and out_dtype.fields is not None:
            # When a FITS file includes a pseudo-unsigned-int column, astropy will return
            # a FITS_rec with an incorrect table dtype.  The following code rebuilds
            # in_dtype from the individual fields, which are correctly labeled with an
            # unsigned int dtype.
            # We can remove this once the issue is resolved in astropy:
            # https://github.com/astropy/astropy/issues/8862
            if isinstance(a, fits.fitsrec.FITS_rec):
                new_in_dtype = []
                updated = False
                for field_name in in_dtype.fields:
                    table_dtype = in_dtype[field_name]
                    field_dtype = a.field(field_name).dtype
                    if np.issubdtype(table_dtype, np.signedinteger) and np.issubdtype(field_dtype, np.unsignedinteger):
                        new_in_dtype.append((field_name, field_dtype))
                        updated = True
                    else:
                        new_in_dtype.append((field_name, table_dtype))
                if updated:
                    in_dtype = np.dtype(new_in_dtype)

            if in_dtype == out_dtype:
                return a
            in_names = {n.lower() for n in in_dtype.names}
            out_names = {n.lower() for n in out_dtype.names}
            if in_names == out_names:
                # Change the dtype name to match the fits record names
                # as the mismatch causes case insensitive access to fail
                out_dtype.names = in_dtype.names
            else:
                raise ValueError(
                    "Column names don't match schema. "
                    "Schema has {0}. Data has {1}".format(
                        str(out_names.difference(in_names)),
                        str(in_names.difference(out_names))))

            new_dtype = []
            for i in range(len(out_dtype.fields)):
                in_type = in_dtype[i]
                out_type = out_dtype[i]
                if in_type.subdtype is None:
                    type_str = in_type.str
                else:
                    type_str = in_type.subdtype[0].str
                if np.can_cast(in_type, out_type, 'equiv'):
                    new_dtype.append(
                        (out_dtype.names[i],
                         type_str,
                         in_type.shape))
                else:
                    return np.asanyarray(a, dtype=out_dtype)
            return a.view(dtype=np.dtype(new_dtype))
        else:
            return np.asanyarray(a, dtype=out_dtype)
    else:
        try:
            a = np.asarray(a, dtype=out_dtype)
        except Exception:
            raise ValueError("Can't convert {0!s} to ndarray".format(type(a)))
        return a


def create_history_entry(description, software=None):
    """
    Create a HistoryEntry object.

    Parameters
    ----------
    description : str
        Description of the change.
    software : dict or list of dict
        A description of the software used.  It should not include
        asdf itself, as that is automatically notated in the
        `asdf_library` entry.

        Each dict must have the following keys:

        ``name``: The name of the software
        ``author``: The author or institution that produced the software
        ``homepage``: A URI to the homepage of the software
        ``version``: The version of the software

    Examples
    --------
    >>> soft = {'name': 'jwreftools', 'author': 'STSCI', \
                'homepage': 'https://github.com/spacetelescope/jwreftools', 'version': "0.7"}
    >>> entry = create_history_entry(description="HISTORY of this file", software=soft)

    """
    from asdf.tags.core import Software, HistoryEntry
    import datetime

    if isinstance(software, list):
        software = [Software(x) for x in software]
    elif software is not None:
        software = Software(software)

    entry = HistoryEntry({
        'description': description,
        'time': datetime.datetime.utcnow()
    })

    if software is not None:
        entry['software'] = software
    return entry


def get_envar_as_boolean(name, default=False):
    """Interpret an environmental as a boolean flag

    Truth is any numeric value that is not 0 or
    any of the following case-insensitive strings:

    ('true', 't', 'yes', 'y')

    Parameters
    ----------
    name : str
        The name of the environmental variable to retrieve

    default : bool
        If the environmental variable cannot be accessed, use as the default.
    """
    truths = ('true', 't', 'yes', 'y')
    falses = ('false', 'f', 'no', 'n')
    if name in os.environ:
        value = os.environ[name]
        try:
            value = bool(int(value))
        except ValueError:
            value_lowcase = value.lower()
            if value_lowcase not in truths + falses:
                raise ValueError(f'Cannot convert value "{value}" to boolean unambiguously.')
            return value_lowcase in truths
        return value

    log.debug(f'Environmental "{name}" cannot be found. Using default value of "{default}".')
    return default


def get_model_type(init):
    """
    Fetch the model type string from the underlying file object.

    Parameters
    ----------
    init : asdf.AsdfFile or astropy.io.fits.HDUList

    Returns
    -------
    str or None
    """
    if isinstance(init, asdf.AsdfFile):
        if "meta" in init:
            return init["meta"].get("model_type")
        else:
            return None
    elif isinstance(init, fits.HDUList):
        return init[0].header.get("DATAMODL")
    else:
        raise TypeError(f"Unhandled init type: {init.__class__.__name__}")
