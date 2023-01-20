"""
Supply a protocol for serializable data.
"""

import os
import typing
from dataclasses import fields, is_dataclass
from typing import (
    Any,
    Dict,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)

import seutil as su
import typing_inspect

from prism.util.radpytools.dataclasses import Dataclass


@runtime_checkable
class Serializable(Protocol):
    """
    A simple protocol for serializable data.
    """

    def dump(
            self,
            output_filepath: os.PathLike,
            fmt: su.io.Fmt = su.io.Fmt.yaml) -> None:
        """
        Serialize data to text file.

        Parameters
        ----------
        output_filepath : os.PathLike
            Filepath to which cache should be dumped.
        fmt : su.io.Fmt, optional
            Designated format of the output file,
            by default `su.io.Fmt.yaml`.
        """
        su.io.dump(output_filepath, self, fmt=fmt)

    @classmethod
    def load(
            cls,
            filepath: os.PathLike,
            fmt: Optional[su.io.Fmt] = None) -> 'Serializable':
        """
        Load a serialized object from file..

        Parameters
        ----------
        filepath : os.PathLike
            Filepath containing repair mining cache.
        fmt : Optional[su.io.Fmt], optional
            Designated format of the input file, by default None.
            If None, then the format is inferred from the extension.

        Returns
        -------
        Serializable
            The deserialized object.
        """
        return su.io.load(filepath, fmt, clz=cls)


_Generic = Any
"""
Surrogate alias for Generic types.

Limitation of available type hints pre-Python 3.10.
"""


def get_typevar_bindings(
        clz) -> Tuple[Union[type,
                            _Generic,
                            Tuple],
                      Dict[TypeVar,
                           type]]:
    """
    Get the type variable bindings for a given class.

    This includes any implicitly bound type variables in base classes.

    Parameters
    ----------
    clz
        A type or generic type alias.

    Returns
    -------
    clz_origin : type
        The unapplied base type.
    Dict[TypeVar, type]
        A map from type variables to their bound types, which may be
        type variables themselves.
    """
    type_bindings: Dict[TypeVar,
                        type] = {}
    clz_origin = typing_inspect.get_origin(clz)
    if clz_origin is None:
        clz_origin = clz
    generic_bases = typing_inspect.get_generic_bases(clz_origin)
    if clz_origin is None and not generic_bases:
        # not generic
        return clz_origin, type_bindings
    clz_args = typing_inspect.get_args(clz)
    type_bindings.update({v: v for v in clz_args if isinstance(v,
                                                               TypeVar)})
    clz_args = list(reversed(clz_args))
    # bind type arguments
    for base in generic_bases:
        _, base_bindings = get_typevar_bindings(base)
        type_bindings.update(
            {
                k: v
                if not isinstance(v,
                                  TypeVar) or not clz_args else clz_args.pop()
                for k,
                v in base_bindings.items()
            })
    return clz_origin, type_bindings


def deserialize_generic_dataclass(
        data: object,
        clz: Type[Dataclass],
        error: str = "ignore") -> Dataclass:
    """
    Deserialize a generic dataclass.

    Especially useful for dataclasses containing inherited or
    uninherited fields annotated with type variables

    Parameters
    ----------
    data : object
        Serialized data, expected to be a dictionary.
    clz : Type[Dataclass]
        A monomorphic type of dataclass that should be deserialized from
        the `data`.
    error : str, optional
        Whether to raise or ignore deserialization errors.
        One of "raise" or "ignore", by default "ignore".

    Returns
    -------
    Dataclass
        An instance of `clz` deserialized from the `data`.

    Raises
    ------
    su.io.DeserializationError
        If the given type is polymorphic or the `clz` is a dataclass but
        `data` is not a dictionary.
    """
    # TODO (AG): Submit as PR to seutil
    clz_origin, bindings = get_typevar_bindings(clz)
    if not bindings or not is_dataclass(clz_origin):
        # not generic
        return su.io.deserialize(data, clz, error)
    clz_origin = typing.cast(type, clz_origin)
    for binding in bindings.values():
        if isinstance(binding, TypeVar):
            raise su.io.DeserializationError(
                data,
                clz,
                "Cannot deserialize polymorphic type")
    if not isinstance(data, dict):
        raise su.io.DeserializationError(
            data,
            clz,
            "Expected dict serialization for dataclass")
    # deserialize the data field by field
    init_field_values: Dict[str,
                            Any] = {}
    non_init_field_values: Dict[str,
                                Any] = {}
    for f in fields(clz_origin):
        if f.name in data:
            field_values = init_field_values if f.init else non_init_field_values
            f_type = typing_inspect.get_origin(f.type)
            if f_type is None:
                f_type = bindings.get(f.type, f.type)
            else:
                # bind type vars
                f_type = f_type.__class_getitem__(
                    tp if not isinstance(tp,
                                         TypeVar) else bindings[tp]
                    for tp in typing_inspect.get_args(f.type))
            field_values[f.name] = deserialize_generic_dataclass(
                data.get(f.name),
                f.type,
                error=error)
    obj = clz_origin(**init_field_values)
    for f_name, f_value in non_init_field_values.items():
        # use object.__setattr__ in case clz is frozen
        object.__setattr__(obj, f_name, f_value)
    return obj
