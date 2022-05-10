"""
Provides utility functions for metadata files.
"""
import os

import seutil as su


def infer_format(filepath: os.PathLike) -> su.io.Fmt:
    """
    Infer format for loading serialized metadata.

    Use this function to infer a value to pass to the ``fmt``
    argument when using ``ProjectMetadata.loads``.

    Parameters
    ----------
    filepath : os.PathLike
        A filepath to a file containing serialized ProjectMetadata.

    Returns
    -------
    su.io.Fmt
        Seutil formatter to handle loading files based on format.

    Raises
    ------
    ValueError
        Exception is raised when file extension of ``filepath`` is
        not an extension supported by any ``su.io.Fmt`` types.

    See Also
    --------
    su.io.Fmt:
        Each enumeration value has a list of valid extensions under
        the ``su.io.Fmt.<name>.exts`` attribute.

    Notes
    -----
    If multiple ``su.io.Fmt`` values have the same extensions,
    (i.e. json, jsonFlexible, jsonPretty, jsonNoSort), the first
    value defined in ``su.io.Fmt`` will be used.
    """
    formatter: su.io.Fmt
    extension = os.path.splitext(filepath)[-1].strip(".")
    for fmt in su.io.Fmt:
        if extension in fmt.exts:
            formatter = fmt
            # Break early, ignore other formatters that may support
            # the extension.
            break
    if formatter is None:
        raise ValueError(
            f"Filepath ({filepath}) has unknown extension ({extension})")
    return formatter
