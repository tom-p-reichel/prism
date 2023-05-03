"""
Defines a class for holding project metadata.
"""

import logging
import typing
from dataclasses import asdict, dataclass, fields
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
)

import seutil as su

from prism.interface.coq.options import SerAPIOptions
from prism.project.util import GitURL
from prism.util.io import Fmt
from prism.util.logging import default_log_level
from prism.util.radpytools import PathLike
from prism.util.radpytools.dataclasses import default_field

from .version_info import version_info

logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel(default_log_level())


@dataclass
class ProjectMetadata:
    """
    Class containing the metadata for a single project.
    """

    immutable_fields: ClassVar[Set[str]] = {
        'project_name',
        'project_url',
        'commit_sha',
        'ocaml_version',
        'coq_version',
        'serapi_version'
    }
    """
    Fields that are defined a priori and cannot be inferred.
    """

    project_name: str
    """
    The unique name of the project in the dataset either literal or
    derived from several auxiliary identifiers.
    """
    build_cmd: List[str]
    """
    Specifies a list of commands for this project (e.g., `build.sh` or
    `make`) that result in building (compiling) the Coq project.
    Commands are presumed to be executed in a shell, e.g., Bash.
    The build commands should not generally install dependencies, which
    should be presumed to already be present.
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
    ocaml_version: Optional[str] = None
    """
    Version of the OCaml compiler with which to build this project.
    If not given, then this metadata is interpreted as the default for
    the project regardless of OCaml compiler version unless overridden
    by a metadata record specifying an `ocaml_version`.
    If `ocaml_version` is given, then `coq_version` must also be given.
    """
    coq_version: Optional[str] = None
    """
    Version of the Coq Proof Assistant used to build this project.
    If not given, then this metadata is interpreted as the default for
    the project regardless of Coq version unless overridden by a
    metadata record specifying a `coq_version`.
     """
    serapi_version: Optional[str] = None
    # HACK: Ideally, this would be an init=False field since it is
    # automatically determined, but seutil.io does not currently support
    # them.
    # Track https://github.com/pengyunie/seutil/issues/30 for
    # resolution
    """
    Version of the API that serializes Coq internal OCaml datatypes
    from/to *S-expressions* or JSON.
    A version of SerAPI must be installed to parse documents for repair.
    The version indicated must be compatible with the specified
    `coq_version`.
    This field is not null if and only if `coq_version` is not null.
    """
    serapi_options: Optional[SerAPIOptions] = None
    """
    Flags or options passed to SerAPI command line executables (e.g.,
    `sercomp`, `sertok`, `sertop`, `sername`, etc.).
    If not given, then the options are presumed to not yet be specified
    and must be inferred later.
    """
    ignore_path_regex: Set[str] = default_field(set())
    """
    Prevents inclusion of inter-project dependencies that are included
    as submodules or subdirectories (such as `CompCert` and
    `coq-ext-lib` in VST).
    Special consideration must be given to these dependencies as they
    affect canonical splitting of training, test and validation datasets
    affecting the performace of the target ML model.
    """
    opam_repos: Set[str] = default_field(set())
    """
    Specifies set of OPAM repositories typically managed through the
    command `opam-repository`.
    An OPAM repository hosts packages that may be required for
    installation of this project.
    Repositories can be registered through subcommands ``add``,
    ``remove``, and ``set-url``, and are updated from their URLs using
    ``opam update``.
    """
    opam_dependencies: Optional[List[str]] = None
    """
    A conjunctive list of OPAM package formulas expressing dependencies
    whose installation is required to build the project.
    The format should generally match that found in the ``depends:``
    field of an OPAM file.
    Coq projects are often built or installed using `make` and
    ``make install`` under the assumption of an existing Makefile for
    the Coq project in dataset, but the `opam_dependencies` are
    typically assumed to be installed prior to running ``make``.
    All OPAM-installable dependencies should be expressed here.
    If not given, then the options are presumed to not yet be specified
    and must be inferred later.
    """
    project_url: Optional[GitURL] = None
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
        if self.serapi_version is None and self.coq_version is not None:
            self.serapi_version = version_info.get_serapi_version(
                self.coq_version)
        elif self.project_url is None and self.commit_sha is not None:
            raise ValueError(
                "A commit cannot be given if the project URL is not given.")
        elif self.ocaml_version is not None and self.coq_version is None:
            raise ValueError(
                "A Coq version must be specified if an OCaml version is given.")
        if not version_info.are_coq_ocaml_compatible(self.coq_version,
                                                     self.ocaml_version):
            raise ValueError(
                f"Incompatible Coq/OCaml versions specified: coq={self.coq_version}, "
                f"ocaml={self.ocaml_version}")
        if not version_info.are_serapi_coq_compatible(self.coq_version,
                                                      self.serapi_version):
            raise ValueError(
                f"Incompatible Coq/SerAPI versions specified: coq={self.coq_version}, "
                f"SerAPI={self.serapi_version}")
        # standardize project url
        if self.project_url is not None:
            self.project_url = GitURL(self.project_url)
        # guard against common kinds of misspecified or misformatted
        # data
        for cmd_seq in ['build_cmd', 'install_cmd', 'clean_cmd']:
            if getattr(self, cmd_seq) is None:
                setattr(self, cmd_seq, [])
            else:
                # remove None commands
                setattr(
                    self,
                    cmd_seq,
                    [cmd for cmd in getattr(self,
                                            cmd_seq) if cmd is not None])
        for (attr,
             tp) in [('opam_repos',
                      set),
                     ('opam_dependencies',
                      lambda x: list(dict.fromkeys(x))),
                     ('ignore_path_regex',
                      set)]:
            if getattr(self, attr) is None:
                if attr != 'opam_dependencies':
                    # opam_dependencies is allowed to be None
                    setattr(self, attr, set())
            else:
                # remove None elements
                setattr(
                    self,
                    attr,
                    tp(e for e in getattr(self,
                                          attr) if e is not None))

    def __gt__(self, other: 'ProjectMetadata') -> bool:
        """
        Return whether this metadata overrides the other metadata.
        """
        if not isinstance(other, ProjectMetadata):
            return NotImplemented
        return other < self

    def __hash__(self) -> int:
        """
        Hash only the fields that identify the metadata.
        """
        return hash(
            (
                self.project_name,
                self.project_url,
                self.commit_sha,
                self.coq_version,
                self.ocaml_version))

    def __lt__(self, other: 'ProjectMetadata') -> bool:
        """
        Return whether the `other` metadata overrides this metadata.

        This defines a partial order over metadata since some metadata
        will not be comparable.
        """
        if not isinstance(other, ProjectMetadata):
            return NotImplemented
        if self.project_name != other.project_name:
            return False
        return (
            other.project_url is not None and self.project_url is None or (
                other.project_url == self.project_url
                and other.commit_sha is not None and self.commit_sha is None)
            or (
                other.project_url == self.project_url
                and other.commit_sha == self.commit_sha
                and other.coq_version is not None and self.coq_version is None)
            or (
                other.project_url == self.project_url
                and other.commit_sha == self.commit_sha
                and other.coq_version == self.coq_version and (
                    other.ocaml_version is not None
                    and self.ocaml_version is None)))

    @property
    def key(self) -> Tuple[str, str, str, str]:
        """
        A key that can be used for total-order sorting of metadata.
        """
        return (
            self.project_name,
            self.commit_sha if self.commit_sha is not None else "None",
            self.coq_version if self.coq_version is not None else "None",
            self.ocaml_version if self.ocaml_version is not None else "None")

    @property
    def level(self) -> int:
        """
        Get the level of the metadata.

        Returns
        -------
        int
            The level of the metadata as determined by the partial order
            of the metadata among comparable metadata, where higher
            levels indicate greater precedence.
        """
        bits = [
            self.coq_version is not None,
            self.ocaml_version is not None,
            self.project_url is not None,
            self.commit_sha is not None,
        ]
        return sum(2**i * b for i, b in enumerate(bits))

    def levels(self,
               reverse: bool = False,
               inclusive: bool = True) -> Iterator['ProjectMetadata']:
        """
        Iterate over views of this metadata at each level.

        Parameters
        ----------
        reverse : bool, optional
            Whether to iterate the levels in descending order (True) or
            in ascending order (False), by default False.
        inclusive : bool, optional
            Whether to include this metadata in the iteration (True) or
            not (False), by default True.

        Yields
        ------
        ProjectMetadata
            A view of this metadata at some level less than or equal to
            its level.
        """
        if reverse:
            levels = range(self.level - (0 if inclusive else 1), -1, -1)
        else:
            levels = range(self.level + (1 if inclusive else 0))
        for i in levels:
            try:
                yield self.at_level(i)
            except ValueError:
                continue

    def at_level(self, level: int) -> 'ProjectMetadata':
        """
        Return a view of this metadata at the given level.

        The level must be less than or equal to the level of this
        metadata.

        Parameters
        ----------
        level : int
            A level

        Returns
        -------
        view : ProjectMetadata
            A view (shallow copy) of this metadata at the requested
            level, i.e., such that ``view.level == level`` is True.

        Raises
        ------
        RuntimeError
            If the view cannot be created because the requested level is
            greater than the level of this metadata.
        """
        self_level = self.level
        if level > self.level or level < 0:
            raise RuntimeError(
                f"Cannot create view at level {level} of metadata at level {self_level}"
            )
        fields = asdict(self)
        if level < self_level:
            if not level & 8:
                fields['commit_sha'] = None
            if not level & 4:
                fields['project_url'] = None
            if not level & 2:
                fields['ocaml_version'] = None
            if not level & 1:
                fields['coq_version'] = None
                fields['serapi_version'] = None
        return ProjectMetadata(**fields)

    def serialize(self) -> Dict[str, Any]:  # noqa: D102
        # workaround for bug in seutil that skips custom serialization
        # for subclasses of primitive types like str
        serialized = {
            f.name: su.io.serialize(getattr(self,
                                            f.name)) for f in fields(self)
        }
        if self.project_url is not None:
            serialized['project_url'] = str(self.project_url)
        return serialized

    @classmethod
    def deserialize(  # noqa: D102
            cls,
            data: Dict[str,
                       Any]) -> 'ProjectMetadata':
        kwargs = {}
        for f in fields(cls):
            try:
                kwargs[f.name] = su.io.deserialize(data[f.name], clz=f.type)
            except KeyError:
                pass
        if 'coq_dependencies' in data:
            logger.warn(
                "The 'coq_dependencies' field is deprecated. "
                "Use 'opam_dependencies' instead.")
            opam_dependencies = kwargs.setdefault('opam_dependencies', [])
            opam_dependencies.extend(data['coq_dependencies'])
        return ProjectMetadata(**kwargs)

    @classmethod
    def dump(
            cls,
            projects: Iterable['ProjectMetadata'],
            output_filepath: PathLike,
            fmt: Fmt = Fmt.yaml) -> None:
        """
        Serialize metadata and writes to .yml file.

        Parameters
        ----------
        projects : Iterable[ProjectMetadata]
            List of `ProjectMetadata` class objects to be serialized.
        output_filepath : PathLike
            Filepath to which metadata should be dumped.
        fmt : Fmt, optional
            Designated format of the output file,
            by default `Fmt.yaml`.
        """
        su.io.dump(str(output_filepath), projects, fmt=fmt)

    @classmethod
    def load(cls,
             filepath: PathLike,
             fmt: Fmt = Fmt.yaml) -> List['ProjectMetadata']:
        """
        Create list of `ProjectMetadata` objects from input file.

        Parameters
        ----------
        filepath : PathLike
            Filepath containing project metadata.
        fmt : Fmt, optional
            Designated format of the input file,
            by default `Fmt.yaml`.

        Returns
        -------
        List[ProjectMetadata]
            List of `ProjectMetadata` objects
        """
        data = typing.cast(List[Dict[str, Any]], su.io.load(str(filepath), fmt))
        project_metadata: List[ProjectMetadata] = [
            su.io.deserialize(project,
                              cls) for project in data
        ]
        return project_metadata
