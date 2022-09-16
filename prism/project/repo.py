"""
Module providing Coq project repository class representations.
"""
from __future__ import annotations

import os
import pathlib
import random
import warnings
from enum import Enum
from typing import List, Optional

import git
from git import Commit, Repo

from prism.data.document import CoqDocument
from prism.language.gallina.parser import CoqParser
from prism.project.base import MetadataArgs, Project
from prism.project.metadata.storage import MetadataStorage
from prism.util.radpytools.os import pushd


class CommitTraversalStrategy(Enum):
    """
    Enum used for describing iteration algorithm.
    """

    NEW_FIRST = 1
    """
    Progress through newer and newer commits
    until all have been finished.
    """
    OLD_FIRST = 2
    """
    Progress through older and older commits
    until all have been finished.
    """
    CURLICUE_NEW = 3
    """
    Alternate newer and older steps progressively
    from the center, assuming the center is a newer
    step.
    """
    CURLICUE_OLD = 4
    """
    Alternate newer and older steps progressively
    from the center, assuming the center is an older
    step.
    """


class CommitIterator:
    """
    Class for handling iteration over a range of commits.
    """

    def __init__(
        self,
        repo: ProjectRepo,
        commit_sha: str,
        march_strategy: Optional[
            CommitTraversalStrategy] = CommitTraversalStrategy.NEW_FIRST):
        """
        Initialize CommitIterator.

        Parameters
        ----------
        repo : ProjectRepo
            Repo, the commits of which we wish to iterate through.

        commit_sha : str
            Initial commit which we wish to treat as the starting point
            for the iteration

        march_strategy : CommitTraversalStrategy
            The particular method of iterating over the repo which
            we wish to use.
        """
        self._repo = repo
        # For the purposes of iteration (whatever the state of the
        # repo when the iterator is constructed) it is assumed that
        # the head of the repo at construction time is the furthest
        # forward that we are interested in traversing.
        self._repo_initial_head = repo.commit(repo.reset_head)
        parent_list = list(repo.commit(self._repo_initial_head).iter_parents())
        self._commits = [self._repo_initial_head] + parent_list
        self._commit_sha = commit_sha
        self._commit_sha_list = [x.hexsha for x in self._commits]
        self._commit_idx = self._commit_sha_list.index(self._commit_sha)
        if self._commit_sha not in self._commit_sha_list:
            raise KeyError("Commit sha supplied to CommitIterator not in repo")

        self._march_strategy = march_strategy
        nmf = CommitTraversalStrategy.NEW_FIRST
        omf = CommitTraversalStrategy.OLD_FIRST
        crn = CommitTraversalStrategy.CURLICUE_NEW
        cro = CommitTraversalStrategy.CURLICUE_OLD
        self._next_func_dict = {
            nmf: self.new_first,
            omf: self.old_first,
            crn: self.curlicue,
            cro: self.curlicue
        }
        self._next_func = self._next_func_dict[self._march_strategy]

        self._last_ret = ""
        self._newest_commit = None
        self._oldest_commit = None
        self.init_commit_indices()

    def __iter__(self):
        """
        Initialize iterator.
        """
        self.init_commit_indices()
        if self._march_strategy == CommitTraversalStrategy.CURLICUE_NEW \
           or self._march_strategy == CommitTraversalStrategy.NEW_FIRST:
            self._last_ret = "old"
            self._newest_commit = self._commit_idx
        elif (self._march_strategy == CommitTraversalStrategy.CURLICUE_OLD
              or self._march_strategy == CommitTraversalStrategy.OLD_FIRST):
            self._last_ret = "new"
            self._oldest_commit = self._commit_idx
        return self

    def __next__(self):
        """
        Return next value in container.
        """
        return self._next_func()

    def init_commit_indices(self):
        """
        Initialize commit indices.

        Initialize the newest and oldest commit indices, according to
        where the starting commit is.
        """
        if self._commit_idx > 0:
            self._newest_commit = self._commit_idx - 1
        else:
            self._newest_commit = None
        if self._commit_idx < len(self._commits) - 1:
            self._oldest_commit = self._commit_idx + 1
        else:
            self._oldest_commit = None

    def set_center_commit(self, sha):
        """
        Reset center commit.
        """
        if sha not in self._commit_sha_list:
            raise KeyError("Commit sha supplied to CommitIterator not in repo")
        self._commit_sha = sha
        self._commit_idx = self._commit_sha_list.index(self._commit_sha)
        self.init_commit_indices()

    def new_first(self):
        """
        Return newer commits until none remain, then older.

        The commit traversal strategy which follows all progressively
        newer commits before it returns older commits.
        """
        if self._newest_commit >= 0:
            tmp_idx = self._newest_commit
            self._newest_commit = self._newest_commit - 1
            return self._commits[tmp_idx]
        elif self._oldest_commit < len(self._commits):
            tmp_idx = self._oldest_commit
            self._oldest_commit = self._oldest_commit + 1
            return self._commits[tmp_idx]
        else:
            raise StopIteration

    def old_first(self):
        """
        Return older commits until none remain, then newer.

        The commit traversal strategy which follows all progressively
        older commits before it returns newer commits.
        """
        if self._oldest_commit < len(self._commits):
            tmp_idx = self._oldest_commit
            self._oldest_commit = self._oldest_commit + 1
            return self._commits[tmp_idx]
        elif self._newest_commit >= 0:
            tmp_idx = self._newest_commit
            self._newest_commit = self._newest_commit - 1
            return self._commits[tmp_idx]
        else:
            raise StopIteration

    def curlicue(self):
        """
        Return commits in a progressively widened area about the center.

        The commit traversal strategy which alternates between newer and
        older commits, progressively widening the distance from the
        central commit.
        """
        if self._newest_commit == 0:
            self._last_ret = "new"
        if self._oldest_commit == len(self._commits):
            self._last_ret = "old"
        if self._last_ret == "old" and self._newest_commit >= 0:
            self._last_ret = "new"
            tmp_idx = self._newest_commit
            self._newest_commit = self._newest_commit - 1
            return self._commits[tmp_idx]
        elif (self._last_ret == "new"
              and self._oldest_commit < len(self._commits)):
            self._last_ret = "old"
            tmp_idx = self._oldest_commit
            self._oldest_commit = self._oldest_commit + 1
            return self._commits[tmp_idx]
        else:
            if self._last_ret != "new" and self._last_ret != "old":
                raise Exception("Malformed")
            else:
                raise StopIteration


class ChangedCoqCommitIterator(CommitIterator):
    """
    Subclass of CommitIterator only yielding changed .v files.
    """

    def __iter__(self):
        """
        Yield each commit in the specified order.

        Excludes commits that did not change a .v file.
        """
        last = None
        super().__iter__()
        # this is possibly the only way
        # to iterate through a superclass
        while True:
            try:
                commit = super().__next__()
            except StopIteration:
                return

            if last is None:
                yield commit
            else:
                changed_files = self._repo.git.diff(
                    "--name-only",
                    commit,
                    last).split("\n")
                if any(filename.endswith(".v") for filename in changed_files):
                    yield commit
            last = commit


class ProjectRepo(Repo, Project):
    """
    Class for representing a Coq project.

    Based on GitPython's `Repo` class.
    """

    def __init__(
            self,
            dir_abspath: os.PathLike,
            *args,
            commit_sha: Optional[str] = None,
            **kwargs):
        """
        Initialize Project object.
        """
        try:
            Repo.__init__(self, dir_abspath)
        except git.exc.NoSuchPathError:
            dir_abspath = pathlib.Path(dir_abspath)
            storage = [a for a in args if isinstance(a, MetadataStorage)]
            if not storage:
                storage = kwargs.get('metadata_storage')
            else:
                storage = storage[0]
            try:
                # try to infer project name from stem
                project_urls = storage.get_project_sources(dir_abspath.stem)
            except KeyError:
                project_urls = set()
            if project_urls:
                # clone from first viable URL
                for project_url in project_urls:
                    try:
                        Repo.clone_from(project_url, dir_abspath)
                    except git.exc.GitCommandError:
                        continue
                    else:
                        break
            else:
                # no viable sources to clone from
                # re-raise original error
                raise
            Repo.__init__(self, dir_abspath)
        Project.__init__(self, dir_abspath, *args, **kwargs)
        self.current_commit_name: Optional[str] = None  # i.e., HEAD
        """
        The name/SHA of the current virtual commit.

        By default None, which serves as an alias for the current index
        HEAD, this attribute controls access to commit files without
        requiring one to actually change the working tree.
        """
        # NOTE (AG): I question the value of this attribute and its
        # current usage and wonder if it could be refactored to
        # something simpler.

        storage = self.metadata_storage

        self.reset_head = self.commit_sha
        """
        The SHA for a commit that serves as a restore point.

        By default, this is defined as the SHA of the checked out commit
        at the time that the `ProjectRepo` is instantiated.
        """

        if commit_sha is not None:
            self.git.checkout(commit_sha)

        self._last_metadata_commit: str = ""

    @property
    def commit_sha(self) -> str:  # noqa: D102
        return self.commit().hexsha

    @property
    def metadata_args(self) -> MetadataArgs:  # noqa: D102
        return MetadataArgs(
            self.remote_url,
            self.commit_sha,
            self.coq_version,
            self.ocaml_version)

    @property
    def name(self) -> str:  # noqa: D102
        # get last non-empty segment of URL
        return pathlib.Path(self.remote_url).stem

    @property
    def path(self) -> os.PathLike:  # noqa: D102
        return self.working_dir

    @property
    def remote_url(self) -> str:  # noqa: D102
        return self.remote().url

    def _get_file(
            self,
            filename: str,
            commit_name: Optional[str] = None) -> CoqDocument:
        """
        Return a specific Coq source file from a specific commit.

        This function may change the git repo HEAD on disk.

        Parameters
        ----------
        filename : str
            The absolute path to the file to return.
        commit_name : str or None, optional
            A commit hash, branch name, or tag name from which to fetch
            the file. Defaults to HEAD.

        Returns
        -------
        CoqDocument
            A CoqDocument corresponding to the selected Coq source file

        Raises
        ------
        ValueError
            If given `filename` does not end in ".v"
        """
        if commit_name is not None:
            warnings.warn(
                "Querying files of a non-checked out commit is deprecated",
                DeprecationWarning)
        commit = self.commit(commit_name)
        self.git.checkout(commit_name)
        # Compute relative path
        rel_filename = filename.replace(commit.tree.abspath, "")[1 :]
        return CoqDocument(
            rel_filename,
            project_path=self.path,
            source_code=CoqParser.parse_source(
                (commit.tree / rel_filename).abspath))

    def _pre_get_file(self, **kwargs):
        """
        Set the current commit; use HEAD if none given.
        """
        self.current_commit_name = kwargs.get("commit_name", None)

    def _pre_get_random(self, **kwargs):
        """
        Set the current commit; use random if none given.
        """
        commit_name = kwargs.get("commit_name", None)
        if commit_name is None:
            kwargs['commit_name'] = self.get_random_commit()
        self._pre_get_file(**kwargs)

    def _traverse_file_tree(self) -> List[CoqDocument]:
        """
        Traverse the file tree and return a full list of file objects.

        This function may change the git repo HEAD on disk.
        """
        if self.current_commit_name is not None:
            warnings.warn(
                "Querying files of a non-checked out commit is deprecated",
                DeprecationWarning)
        self.git.checkout(self.current_commit_name)
        with pushd(self.path):
            return [
                CoqDocument(
                    f,
                    project_path=self.path,
                    source_code=CoqParser.parse_source(f))
                for f in self.get_file_list(relative=True)
            ]

    def get_file_list(
            self,
            relative: bool = False,
            dependency_order: bool = False,
            commit_name: Optional[str] = None) -> List[str]:
        """
        Return a list of all Coq files associated with this project.

        Parameters
        ----------
        relative : bool, optional
            Whether to return absolute file paths or paths relative to
            the root of the project, by default False.
        dependency_order : bool, optional
            Whether to return the files in dependency order or not, by
            default False.
            Dependency order means that if one file ``foo`` depends
            upon another file ``bar``, then ``bar`` will appear
            before ``foo`` in the returned list.
            If False, then the files are sorted lexicographically.
        commit_name : str or None, optional
            A commit hash, branch name, or tag name from which to get
            the file list. This is HEAD by default.

        Returns
        -------
        List[str]
            The list of absolute (or `relative`) paths to all Coq files
            in the project sorted according to `dependency_order`, not
            including those ignored by `ignore_path_regex`.
        """
        if commit_name is not None:
            warnings.warn(
                "Querying files of a non-checked out commit is deprecated",
                DeprecationWarning)
            return self.filter_files(
                self.commit(commit_name).tree.traverse(),
                relative,
                dependency_order)
        else:
            return super().get_file_list(relative, dependency_order)

    def get_random_commit(self) -> Commit:
        """
        Return a random `Commit` object from the project repo.

        Returns
        -------
        Commit
            A random `Commit` object from the project repo
        """

        def _get_hash(commit: Commit) -> str:
            return commit.hexsha

        commit_hashes = list(map(_get_hash, self.iter_commits('--all')))
        chosen_hash = random.choice(commit_hashes)
        result = self.commit(chosen_hash)
        return result

    def get_random_file(self, commit_name: Optional[str] = None) -> CoqDocument:
        """
        Return a random Coq source file from the repo.

        The commit may be specified or left to be chosen at radnom.

        Parameters
        ----------
        commit_name : str or None
            A commit hash, branch name, or tag name indicating where
            the file should be selected from. If None, commit is chosen
            at random.

        Returns
        -------
        CoqDocument
            A random Coq source file in the form of a CoqDocument
        """
        return super().get_random_file(commit_name=commit_name)

    def get_random_sentence(
            self,
            filename: Optional[str] = None,
            glom_proofs: bool = True,
            commit_name: Optional[str] = None) -> str:
        """
        Return a random sentence from the project.

        Filename and commit are random unless they are provided.

        Parameters
        ----------
        filename : Optional[str], optional
            Absolute path to file to load sentence from, by default None
        glom_proofs : bool, optional
            Boolean flag indicating whether proofs should form their own
            pseudo-sentences, by default True
        commit_name : Optional[str], optional
            Commit name (hash, branch name, tag name) to load sentence
            from, by default None

        Returns
        -------
        str
            A random sentence from the project
        """
        return super().get_random_sentence(
            filename,
            glom_proofs,
            commit_name=commit_name)

    def get_random_sentence_pair_adjacent(
            self,
            filename: Optional[str] = None,
            glom_proofs: bool = True,
            commit_name: Optional[str] = None) -> List[str]:
        """
        Return a random adjacent sentence pair from the project.

        Filename and commit are random unless they are provided.

        Parameters
        ----------
        filename : Optional[str], optional
            Absolute path to file to load sentences from, by default
            None
        glom_proofs : bool, optional
            Boolean flag indicating whether proofs should form their own
            pseudo-sentences, by default True
        commit_name : Optional[str], optional
            Commit name (hash, branch name, tag name) to load sentences
            from, by default None

        Returns
        -------
        List of str
            A list of two adjacent sentences from the project, with the
            first sentence chosen at random
        """
        return super().get_random_sentence_pair_adjacent(
            filename,
            glom_proofs,
            commit_name=commit_name)
