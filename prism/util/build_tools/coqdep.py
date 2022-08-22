"""
Provides an object-oriented abstraction of OPAM switches.
"""
import networkx as nx
from os import PathLike
from typing import List

from networkx.algorithms.dag import all_topological_sorts

from prism.util.opam.switch import OpamSwitch


def check_valid_topological_sort(dep_graph: nx.DiGraph, dep_list: List[str]):
    """
    Determine whether the given topological sort of files is valid.

    Parameters
    ----------
    dep_graph : networkx.DiGraph
        Graph representing dependencies of the given set of files.
    dep_list : List[str]
        A particular ordering of the nodes in the dependency graph.

    Returns
    -------
    valid : bool
        Whether the ordering represents a topological sort.
    """
    return dep_list in list(all_topological_sorts(dep_graph))


def make_dependency_graph(
        files: List[PathLike],
        switch: OpamSwitch,
        IQR: str = '',
        boot: bool = False):
    """
    Return directed graph of dependencies for supplied files.

    Parameters
    ----------
    files : List[PathLike]
        List of files to be submitted to coqdep
    switch : OpamSwitch
        Used for execution of coqdep in the proper environment
    IQR : str, optional
        IQR flags for coqdep
    boot : bool
        Flag indicating whether to include the -boot option in
        the `coqdep` command

    Returns
    -------
    dep_graph : networkx.DiGraph
    """
    dep_graph_dict = {}
    for file in files:
        dep_graph_dict[file + "o"] = get_dependencies(file, switch, IQR, boot)
    dep_graph = nx.DiGraph(dep_graph_dict)
    return dep_graph


def get_dependencies(
        file: PathLike,
        switch: OpamSwitch,
        IQR: str = '',
        boot: bool = False):
    """
    Return dependencies for the given file.

    Parameters
    ----------
    files : PathLike
        Path of files to be submitted to coqdep
    switch : OpamSwitch
        Used for execution of coqdep in the proper environment
    IQR : str, optional
        IQR flags for coqdep
    boot : bool
        Flag indicating whether to include the -boot option in
        the `coqdep` command

    Returns
    -------
    file_deps : List[str]
        List of '.vo' files which the supplied file depend on.
    """
    if boot:
        boot = '-boot'
    else:
        boot = ''
    command = "coqdep {0} -sort {1} {2}".format(file, IQR, boot)
    file_deps = switch.run(command)
    file_deps = file_deps.stdout.strip().replace("./", "").split(" ")
    file_deps.remove(file + "o")
    return file_deps


def order_dependencies(
        files: List[PathLike],
        switch: OpamSwitch,
        IQR: str = '',
        boot: bool = False):
    """
    Return sorted dependencies for supplied files.

    Parameters
    ----------
    files : List[PathLike]
        List of files to be submitted to coqdep
    switch : OpamSwitch
        Used for execution of coqdep in the proper environment
    IQR : str, optional
        IQR flags for coqdep
    boot : bool
        Flag indicating whether to include the -boot option in
        the `coqdep` command

    Returns
    -------
    file_deps : List[str]
        List of '.vo' files in order of least to most dependent
    """
    files = ' '.join(files)
    if boot:
        boot = '-boot'
    else:
        boot = ''
    command = "coqdep {0} -sort {1} {2}".format(files, IQR, boot)
    file_deps = switch.run(command)
    file_deps = file_deps.stdout.strip().split(" ")
    print(file_deps)
    return file_deps
