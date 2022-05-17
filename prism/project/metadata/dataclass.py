"""
Contains all metadata related to paticular GitHub repositories.
"""

import os
# from collections.abc import Iterable
from dataclasses import dataclass
from typing import Iterable, List, Optional

import seutil as su
from radpytools.dataclasses import default_field


@dataclass
class ProjectMetadata:
    """
    Class containing the metadata for a single project.
    """

    project_name: str
    """
    The unique name of the project in the dataset either literal or
    derived from several auxiliary identifiers.
    """
    serapi_options: str
    """
    Flags or options passed to SerAPI command line executables (e.g.,
    `sercomp`, `sertok`, `sertop`, `sername`, etc.).
    """
    build_cmd: List[str]
    """
    Specifies a list of commands for this project (e.g., `build.sh` or
    `make`) that result in building (compiling) the Coq project.
    Commands are presumed to be executed in a shell, e.g., Bash.
    """
    install_cmd: List[str]
    """
    Specifies a list of commands for this project (e.g., `install.sh`
    or `make install`) that result in installing the Coq project to the
    user's local package index, thus making the package available for
    use as a dependency by other projects.
    The project may be presumed to have been built using `build_cmd`
    before the sequence of commands in `install_cmd`.
    Commands are presumed to be executed in a shell, e.g., Bash.
    """
    clean_cmd: List[str]
    """
    Specifies a list of commands for removing executables, object files,
    and other artifacts from building the project (e.g., `make clean`).
    Commands are presumed to be executed in a shell, e.g., Bash.
    """
    coq_version: Optional[str] = None
    """
    Version of the Coq Proof Assistant used to build this project.
    This field provides support for datasets containing commits across
    multiple Coq versions.
    If not given, then this metadata is interpreted as the default for
    the project regardless of Coq version unless overridden by a
    metadata record specifying a `coq_version`.
     """
    serapi_version: Optional[str] = None
    """
    Version of the API that serializes Coq internal OCaml datatypes
    from/to *S-expressions* or JSON.
    A version of SerAPI must be installed to parse documents for repair.
    The version indicated must be compatible with the specified
    `coq_version`.
    This field is not null if and only if `coq_version` is not null.
    """
    ignore_path_regex: List[str] = default_field([])
    """
    Prevents inclusion of inter-project dependencies that are included
    as submodules or subdirectories (such as `CompCert` and
    `coq-ext-lib` in VST).
    Special consideration must be given to these dependencies as they
    affect canonical splitting of training, test and validation datasets
    affecting the performace of the target ML model.
    """
    coq_dependencies: List[str] = default_field([])
    """
    List of dependencies on packages referring to Coq formalizations and
    plugins that are packaged using OPAM and whose installation is
    required to build this project.
    A string ``pkg`` in `coq_dependencies` should be given such that
    ``opam install pkg`` results in installing the named dependency.
    Coq projects are often built or installed using `make` and
    ``make install`` under the assumption of an existing Makefile for
    the Coq project in dataset, but the `coq_dependencies` are
    typically assumed to be installed prior to running ``make``.
    Only dependencies that are not handled by the project's build system
    should be listed here.
    """
    opam_repos: List[str] = default_field([])
    """
    Specifies list of OPAM repositories typically managed through the
    command `opam-repository`.
    An OPAM repository hosts packages that may be required for
    installation of this project.
    Repositories can be registered through subcommands ``add``,
    ``remove``, and ``set-url``, and are updated from their URLs using
    ``opam update``.
    """
    opam_dependencies: List[str] = default_field([])
    """
    List of non-Coq OPAM dependencies whose installation is required to
    build the project.
    A string ``pkg`` in `opam_dependencies` should be given such that
    ``opam install pkg`` results in installing the named dependency.
    Coq projects are often built or installed using `make` and
    ``make install`` under the assumption of an existing Makefile for
    the Coq project in dataset, but the `coq_dependencies` are typically
    assumed to be installed prior to running ``make``.
    Only dependencies that are not handled by the project's build system
    need to be listed here.
    """
    project_url: Optional[str] = None
    """
    If available, this is the URL hosting the authoritative source code
    or repository (e.g., Git) of a particular project in the dataset.
    If not given, then this metadata is interpreted as the default for
    the project regardless of origin unless overridden by a metadata
    record specifying a `project_url`.
    """
    commit_sha: Optional[str] = None
    """
    Identifies a commit within the repository identified by
    `project_url`.
    It serves as an additional identifier for a project (in a
    particular version) in the dataset.
    A comparison with the SHA of the first commit on the master branch
    will be necessary for ensuring the uniqueness of the project
    identifier.
    The commit must be null if `project_url` is null.
    If the commit is null, then this metadata is interpreted as the
    default for the indicated repository unless overridden by a metadata
    record specifying a `commit_sha`.
    """

    def __post_init__(self) -> None:
        """
        Perform integrity and constraint checking.
        """
        if (self.serapi_version is None) != (self.coq_version is None):
            raise ValueError(
                "`serapi_version` must specified if and only if "
                "`coq_version` is specified.")
        elif self.project_url is None and self.commit_sha is not None:
            raise ValueError(
                "A commit cannot be given if the project URL is not given.")

    def __lt__(self, other: 'ProjectMetadata') -> bool:
        """
        Return whether the `other` metadata overrides this metadata.

        This defines a partial order over metadata since some metadata
        will not be comparable.
        """
        return (
            self.project_name == other.project_name and (
                other.project_url is not None and self.project_url is None
                or other.commit_sha is not None and self.commit_sha is None
                or other.coq_version is not None and self.coq_version is None))

    @classmethod
    def dump(
            cls,
            projects: Iterable['ProjectMetadata'],
            output_filepath: os.PathLike,
            fmt: su.io.Fmt = su.io.Fmt.yaml) -> None:
        """
        Serialize metadata and writes to .yml file.

        Parameters
        ----------
        projects : Iterable[ProjectMetadata]
            List of `ProjectMetadata` class objects to be serialized
        output_filepath : os.PathLike
            Filepath of YAML file to be written containing metadata
            for projects
        fmt : su.io.Fmt, optional
            Designated format of the output file,
            by default su.io.Fmt.yaml
        """
        su.io.dump(output_filepath, projects, fmt=fmt)

    @classmethod
    def load(cls,
             filepath: os.PathLike,
             fmt: su.io.Fmt = su.io.Fmt.yaml) -> List['ProjectMetadata']:
        """
        Create list of `ProjectMetadata` objects from input file.

        Parameters
        ----------
        filepath : os.PathLike
            Filepath of YAML file containing project metadata
        fmt : su.io.Fmt, optional
            Designated format of the input file,
            by default su.io.Fmt.yaml

        Returns
        -------
        List[ProjectMetadata]
            List of `ProjectMetadata` objects
        """
        data = su.io.load(filepath, fmt)
        project_metadata: List[ProjectMetadata] = [
            su.io.deserialize(project,
                              cls) for project in data
        ]
        return project_metadata
