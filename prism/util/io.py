"""
Provides utility functions for serialized data files.
"""
import os
import tempfile
import typing
from pathlib import Path
from typing import IO, TYPE_CHECKING, Optional, Union

import ujson
import yaml
from seutil.io import Fmt, FmtProperty, infer_fmt_from_ext

if TYPE_CHECKING:
    from prism.util.serialize import Serializable

# override Fmt enums on import
type.__setattr__(
    Fmt,
    'json',
    FmtProperty(
        writer=lambda f,
        obj: ujson.dump(obj,
                        typing.cast(IO[str],
                                    f),
                        sort_keys=True),
        reader=lambda f: ujson.load(typing.cast(IO[str],
                                                f)),
        serialize=True,
        exts=["json"],
    ))
type.__setattr__(
    Fmt,
    'jsonFlexible',
    Fmt.json._replace(reader=lambda f: yaml.load(f,
                                                 Loader=yaml.CLoader)))
type.__setattr__(
    Fmt,
    'jsonPretty',
    Fmt.json._replace(
        writer=lambda f,
        obj: ujson.dump(obj,
                        f,
                        sort_keys=True,
                        indent=4),
    ))
type.__setattr__(
    Fmt,
    'jsonNoSort',
    Fmt.json._replace(writer=lambda f,
                      obj: ujson.dump(obj,
                                      f,
                                      indent=4),
                      ))
type.__setattr__(
    Fmt,
    'jsonList',
    FmtProperty(
        writer=lambda item: ujson.dumps(item),
        reader=lambda line: ujson.loads(typing.cast(str,
                                                    line)),
        exts=["jsonl"],
        line_mode=True,
        serialize=True,
    ))
type.__setattr__(
    Fmt,
    'yaml',
    FmtProperty(
        writer=lambda f,
        obj: yaml.dump(
            obj,
            f,
            encoding="utf-8",
            default_flow_style=False,
            Dumper=yaml.CDumper),
        reader=lambda f: yaml.load(f,
                                   Loader=yaml.CLoader),
        serialize=True,
        exts=["yml",
              "yaml"],
    ))


def infer_format(filepath: os.PathLike) -> Fmt:
    """
    Infer format for loading serialized data.

    Parameters
    ----------
    filepath : os.PathLike
        A filepath to a file containing serialized data.

    Returns
    -------
    Fmt
        `seutil` format to handle loading files based on format.

    Raises
    ------
    ValueError
        Exception is raised when file extension of `filepath` is
        not an extension supported by any `Fmt` format.

    See Also
    --------
    Fmt
        Each enumeration value has a list of valid extensions under
        the ``Fmt.<name>.exts`` attribute.

    Notes
    -----
    If multiple ``Fmt`` values have the same extensions,
    (i.e. json, jsonFlexible, jsonPretty, jsonNoSort), the first
    value defined in ``Fmt`` will be used.
    """
    formatter: Optional[Fmt]
    formatter = None
    extension = os.path.splitext(filepath)[-1].strip(".")
    for fmt in Fmt:
        if extension in fmt.exts:
            formatter = fmt
            # Break early, ignore other formatters that may support
            # the extension.
            break
    assert formatter is not None
    if formatter is None:
        raise ValueError(
            f"Filepath ({filepath}) has unknown extension ({extension})")
    return formatter


def atomic_write(
        full_file_path: Path,
        file_contents: Union[str,
                             'Serializable']):
    r"""
    Write a message or object to a text file.

    Any existing file contents are overwritten.

    Parameters
    ----------
    full_file_path : Path
        Full file path, including directory, filename, and extension, to
        write to
    file_contents : Union[str, Serializable]
        The contents to write or serialized to the file.

    Raises
    ------
    TypeError
        If `file_contents` is not a string or `Serializable`.
    """
    # TODO: Refactor to avoid circular import
    from prism.util.serialize import Serializable
    if not isinstance(file_contents, (str, Serializable)):
        raise TypeError(
            f"Cannot write object of type {type(file_contents)} to file")
    fmt_ext = full_file_path.suffix  # contains leading period
    directory = full_file_path.parent
    if not directory.exists():
        os.makedirs(str(directory))
    # Ensure that we write atomically.
    # First, we write to a temporary file so that if we get
    # interrupted, we aren't left with a corrupted file.
    with tempfile.NamedTemporaryFile("w",
                                     delete=False,
                                     dir=directory,
                                     encoding='utf-8') as f:
        if isinstance(file_contents, str):
            f.write(file_contents)
    if isinstance(file_contents, Serializable):
        fmt = infer_fmt_from_ext(fmt_ext)
        f_name = file_contents.dump(f.name, fmt)
        if str(f_name) != f.name:
            # redirected, atomically move the file to final path
            os.replace(f_name, full_file_path.with_suffix(f_name.suffix))
    # Then, we atomically move the file to the correct, final
    # path.
    os.replace(f.name, full_file_path)
