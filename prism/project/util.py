"""
Common project-related utilities.
"""

import os
import urllib.parse
from pathlib import Path
from re import sub
from typing import Set, Union

URL = str


class GitURL(str):
    """
    A Git repository URL either ending in ``".git"`` or not.
    """

    def __new__(cls, content: str):
        """
        Standardize representation by removing ``".git"`` suffix.
        """
        if content.endswith(".git"):
            content = content[:-4]
        return str.__new__(cls, content)

    def __eq__(self, other: object) -> bool:
        """
        Return whether two URLs are equal.

        Equality is invariant to the presence of ``".git"`` suffixes.
        For example, ``GitURL("x.git") == "x"`` evaluates to True.
        """
        if not isinstance(other, str) or isinstance(other, GitURL):
            return super().__eq__(other)
        else:
            return self == GitURL(other)

    def __hash__(self) -> int:  # noqa: D105
        return super().__hash__()


def camel_case_names(name: str) -> Set[str]:
    """
    Return name but in camel case format.

    Dashes and underscores are interpreted as
    delimiters between two words that will be
    concatenated together in camel case.

    Parameters
    ----------
    name : str
        A string representation of a project name.

    Returns
    -------
    Set[str]
        Camel case variations of the name.
    """
    names = set()
    names.add(sub(r"(-)+", " ", name).title().replace(" ", ""))
    names.add(sub(r"(_)+", " ", name).title().replace(" ", ""))
    names.add(sub(r"(-|_)+", " ", name).title().replace(" ", ""))
    parts = name.split("coq")
    parts = [part.title() for part in parts]
    names.add('Coq'.join(parts))
    return names


def extract_name(url: Union[URL, os.PathLike]) -> str:
    """
    Get project name from url or path.

    Parameters
    ----------
    url :  Union[URL, os.PathLike]
        A URL or path to an existing project or repository.

    Returns
    -------
    str
        The name of the project.
    """
    url = str(url)
    fork = Path(urllib.parse.urlparse(url.strip()).path)
    return fork.stem


def name_variants(name: str) -> Set[str]:
    """
    Return different variations of project name.

    Parameters
    ----------
    name : str
        Project name returned from ``extract_name``.

    Returns
    -------
    Set[str]
        A set of names that the project may be referred by
        inside of project language.
    """
    variants = set()
    variants.add(name)
    lower = name.lower()
    if lower != name:
        variants.add(lower)
    # When name is derived from a repository url, it may
    # the dashes and underscores in it. Find ways
    # the library name may be formatted without them.
    variants.add(name.replace('-', ''))
    variants.add(name.replace('-', '_'))
    variants = variants.union(camel_case_names(name))

    # Some projects may coq as a prefix, suffix, or in middle.
    # but not in the logical name.
    if '-coq' in name:
        variants = variants.union(name_variants(name.replace('-coq', '')))
    if 'coq-' in name:
        variants = variants.union(name_variants(name.replace('coq-', '')))
    if '-coq-' in name:
        variants = variants.union(name_variants(name.replace('-coq-', '')))
    return variants