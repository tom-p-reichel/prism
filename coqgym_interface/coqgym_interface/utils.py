"""
Utilities module for CoqGym interface.
"""
import random
import re
from typing import List, Optional, Union

from git import Blob, Commit, Repo


class Project(Repo):
    """
    Class for representing a Coq project.

    Based on GitPython's `Repo` class.
    """

    proof_enders = ["Qed.", "Save.", "Defined.", "Admitted.", "Abort."]

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

    def get_random_file(self, commit_name: Optional[str] = None) -> Blob:
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
        Blob
            A random Coq source file in the form of a Blob
        """
        if commit_name is None:
            commit_name = self.get_random_commit()
        commit = self.commit(commit_name)
        # This should traverse the tree to get all files at all levels
        files = commit.tree.traverse()

        def _select_coq_files(x: Blob) -> bool:
            if x.abspath.endswith(".v"):
                return True
            else:
                return False

        files = list(filter(_select_coq_files, files))
        result = random.choice(files)
        return result

    def get_file(self, filename: str, commit_name: str = 'master') -> Blob:
        """
        Return a specific Coq source file from a specific commit.

        Parameters
        ----------
        filename : str
            The absolute path to the file to return.
        commit_name : str
            A commit hash, branch name, or tag name from which to fetch
            the file. This is 'master' by default.

        Returns
        -------
        Blob
            A Blob corresponding to the selected Coq source file
        """
        commit = self.commit(commit_name)
        for blob in commit.tree.traverse():
            if blob.abspath == filename:
                return blob

    @staticmethod
    def _decode_byte_stream(byte_stream: bytes, encoding: str = 'utf-8') -> str:
        return byte_stream.decode(encoding)

    @staticmethod
    def _strip_comments(
            file_contents: Union[str,
                                 bytes],
            encoding: str = 'utf-8') -> str:
        comment_pattern = r"[(]+\*(.|\n|\r)*?\*[)]+"
        if isinstance(file_contents, bytes):
            file_contents = Project._decode_byte_stream(file_contents, encoding)
        str_no_comments = re.sub(comment_pattern, '', file_contents)
        return str_no_comments

    @staticmethod
    def split_by_sentence(
            file_contents: Union[str,
                                 bytes],
            encoding: str = 'utf-8',
            glom_proofs: bool = True) -> List[str]:
        """
        Split the Coq file text by sentences.

        By default, proofs are then re-glommed into their own entries.
        This behavior can be switched off.

        Parameters
        ----------
        file_contents : Union[str, bytes]
            Complete contents of the Coq source file, either in
            bytestring or string form.
        encoding : str, optional
            The encoding to use for decoding if a bytestring is
            provided, by default 'utf-8'
        glom_proofs : bool, optional
            A flag indicating whether or not proofs should be re-glommed
            after sentences are split, by default `True`

        Returns
        -------
        List[str]
            A list of strings corresponding to Coq source file
            sentences, with proofs glommed (or not) depending on input
            flag.
        """
        if isinstance(file_contents, bytes):
            file_contents = Project._decode_byte_stream(file_contents, encoding)
        file_contents_no_comments = Project._strip_comments(
            file_contents,
            encoding)
        # Split sentences by instances of periods followed by
        # whitespace.
        sentences = re.split(r"\.\s", file_contents_no_comments)
        for i in range(len(sentences)):
            # Replace any whitespace or groups of whitespace with a
            # single space.
            sentences[i] = re.sub(r"(\s)+", " ", sentences[i])
            sentences[i] = sentences[i].strip()
            sentences[i] += "."
        if glom_proofs:
            # Reconstruct proofs onto one line.
            result = []
            idx = 0
            while idx < len(sentences):
                # Proofs can start with "Proof. " or "Proof <other
                # words>."
                if sentences[idx] == "Proof." or sentences[idx].startswith(
                        "Proof "):
                    intermediate_list = []
                    while sentences[idx] not in Project.proof_enders:
                        intermediate_list.append(sentences[idx])
                        idx += 1
                    intermediate_list.append(sentences[idx])
                    result.append(" ".join(intermediate_list))
                else:
                    result.append(sentences[idx])
                idx += 1
            # Lop off the final line if it's just a period, i.e., blank.
            if result[-1] == ".":
                result.pop()
        else:
            result = sentences
        return result


def main():
    """
    Test module functionality.
    """
    repo_folder = "../data/CompCert"
    compcert_repo = Project(repo_folder)
    random_file = compcert_repo.get_random_file()
    ds = random_file.data_stream
    output = ds.read()
    for line in Project._decode_byte_stream(output).split('\n'):
        print(line)
    print('*************************************')
    split_contents = Project.split_by_sentence(output)
    for line in split_contents:
        print(line)
    print("File:", random_file.abspath)


if __name__ == "__main__":
    main()
