"""
Test module for prism.data.project module.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import unittest
from itertools import chain
from pathlib import Path

import git

from prism.data.document import CoqDocument
from prism.project.base import SEM, Project, SentenceExtractionMethod
from prism.project.metadata.dataclass import ProjectMetadata
from prism.project.metadata.storage import MetadataStorage
from prism.project.repo import ProjectRepo
from prism.tests import _COQ_EXAMPLES_PATH
from prism.util.opam.switch import OpamSwitch


class TestProject(unittest.TestCase):
    """
    Test suite for Project class.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up shared project files for unit tests.
        """
        expected_filename = os.path.join(
            _COQ_EXAMPLES_PATH,
            "split_by_sentence_expected.json")
        cls.test_contents = {}
        cls.document = {}
        cls.test_list = {}
        cls.test_glom_list = {}
        coq_example_files = ["simple", "nested", "Alphabet"]
        for coq_file in coq_example_files:
            test_filename = os.path.join(_COQ_EXAMPLES_PATH, f"{coq_file}.v")
            with open(test_filename, "rt") as f:
                cls.test_contents[coq_file] = f.read()
            cls.document[coq_file] = CoqDocument(
                test_filename,
                cls.test_contents[coq_file],
                project_path=_COQ_EXAMPLES_PATH)
            with open(expected_filename, "rt") as f:
                contents = json.load(f)
                cls.test_list[coq_file] = contents[f"{coq_file}_test_list"]
                cls.test_glom_list[coq_file] = contents[
                    f"{coq_file}_test_glom_list"]
        # set up artifacts for test_build_and_get_igr
        test_path = Path(__file__).parent
        repo_path = test_path / "coq-sep-logic"
        if not os.path.exists(repo_path):
            test_repo = git.Repo.clone_from(
                "https://github.com/tchajed/coq-sep-logic",
                repo_path)
        else:
            test_repo = git.Repo(repo_path)
        metadata = ProjectMetadata.load(
            _COQ_EXAMPLES_PATH / "coq_sep_logic.yml")[0]
        storage = MetadataStorage()
        storage.insert(metadata.at_level(0))
        storage.insert(metadata)
        test_repo.git.checkout(metadata.commit_sha)
        cls.test_iqr_project = ProjectRepo(
            repo_path,
            metadata_storage=storage,
            sentence_extraction_method=SEM.HEURISTIC,
            num_cores=8)
        # Complete pre-req setup.
        # Use the default switch since there are no dependencies beyond
        # Coq and the package will not be installed.
        switch = OpamSwitch()
        coq_version = switch.get_installed_version("coq")
        if switch.get_installed_version("coq") is None:
            coq_version = "8.10.2"
            switch.install("coq", coq_version, yes=True)
        cls.assertFalse(TestProject(), metadata.opam_repos)
        for repo in metadata.opam_repos:
            switch.add_repo(*repo.split())
        cls.assertFalse(TestProject(), metadata.opam_dependencies)
        cls.assertFalse(TestProject(), metadata.coq_dependencies)
        for dep in chain(metadata.opam_dependencies, metadata.coq_dependencies):
            output = dep.split(".", maxsplit=1)
            if len(output) == 1:
                pkg = output[0]
                ver = None
            else:
                pkg, ver = output
            switch.install(pkg, ver)

    @classmethod
    def tearDownClass(cls) -> None:
        """
        Clean up build artifacts produced as test side-effects.
        """
        repo_path = cls.test_iqr_project.path
        shutil.rmtree(repo_path)

    def test_extract_sentences_heuristic(self):
        """
        Test method for splitting Coq code by sentence.
        """
        for coq_file, document in self.document.items():
            with self.subTest(coq_file):
                actual_outcome = Project.extract_sentences(
                    document,
                    glom_proofs=False,
                    sentence_extraction_method=SEM.HEURISTIC)
                self.assertEqual(actual_outcome, self.test_list[coq_file])

    def test_extract_sentences_heuristic_glom(self):
        """
        Test method for splitting Coq code by sentence.
        """
        for coq_file, document in self.document.items():
            with self.subTest(coq_file):
                actual_outcome = Project.extract_sentences(
                    document,
                    glom_proofs=True,
                    sentence_extraction_method=SEM.HEURISTIC)
                self.assertEqual(actual_outcome, self.test_glom_list[coq_file])

    def test_extract_sentences_serapi(self):
        """
        Test method for splitting Coq code using SERAPI.
        """
        test_path = os.path.dirname(__file__)
        repo_path = os.path.join(test_path, "circuits")
        if not os.path.exists(repo_path):
            test_repo = git.Repo.clone_from(
                "https://github.com/coq-contribs/circuits",
                repo_path)
        else:
            test_repo = git.Repo(repo_path)
        # Checkout HEAD of master as of March 14, 2022
        master_hash = "f2cec6067f2c58e280c5b460e113d738b387be15"
        test_repo.git.checkout(master_hash)
        old_dir = os.path.abspath(os.curdir)
        os.chdir(repo_path)
        subprocess.run("make")
        document = CoqDocument(name="ADDER/Adder.v", project_path=repo_path)
        with open(document.abspath, "rt") as f:
            document.source_code = f.read()
        sentences = Project.extract_sentences(
            document,
            sentence_extraction_method=SentenceExtractionMethod.SERAPI,
            glom_proofs=False)
        for sentence in sentences:
            self.assertTrue(
                sentence.endswith('.') or sentence == '{' or sentence == "}"
                or sentence.endswith("-") or sentence.endswith("+")
                or sentence.endswith("*"))
        # Clean up
        os.chdir(old_dir)
        del test_repo
        shutil.rmtree(os.path.join(repo_path))

    def test_extract_sentences_serapi_simple(self):
        """
        Test method for splitting Coq code using SERAPI.
        """
        for coq_file, document in self.document.items():
            with self.subTest(coq_file):
                actual_outcome = Project.extract_sentences(
                    document,
                    glom_proofs=False,
                    sentence_extraction_method=SEM.SERAPI)
                self.assertEqual(actual_outcome, self.test_list[coq_file])

    def test_extract_sentences_serapi_simple_glom(self):
        """
        Test proof glomming with serapi-based sentence extractor.
        """
        for coq_file, document in self.document.items():
            with self.subTest(coq_file):
                actual_outcome = Project.extract_sentences(
                    document,
                    glom_proofs=True,
                    sentence_extraction_method=SEM.SERAPI)
                self.assertEqual(actual_outcome, self.test_glom_list[coq_file])

    def test_extract_sentences_serapi_glom_nested(self):
        """
        Test glomming with serpai-based extractor w/ nested proofs.

        This test is disabled for now until a good caching scheme can be
        developed for a built GeoCoq. However, it does pass as of
        2022-04-19.
        """
        return
        project_name = "GeoCoq"
        master_hash = "25917f56a3b46843690457b2bfd83168bed1321c"
        target_project = "GeoCoq/GeoCoq"
        test_path = os.path.dirname(__file__)
        repo_path = os.path.join(test_path, project_name)
        if not os.path.exists(repo_path):
            test_repo = git.Repo.clone_from(
                "https://github.com/" + target_project,
                repo_path)
        else:
            test_repo = git.Repo(repo_path)
        # Checkout HEAD of master as of March 14, 2022
        test_repo.git.checkout(master_hash)
        old_dir = os.path.abspath(os.curdir)
        os.chdir(repo_path)
        subprocess.run("./configure.sh")
        subprocess.run("make")
        document = CoqDocument(
            name="Tactics/Coinc/CoincR.v",
            project_path=repo_path)
        with open(document.abspath, "rt") as f:
            document.source_code = f.read()
        actual_outcome = Project.extract_sentences(
            document,
            sentence_extraction_method=SentenceExtractionMethod.SERAPI,
            glom_proofs=True)
        for sentence in actual_outcome:
            self.assertTrue(sentence.endswith('.'))
        # Clean up
        os.chdir(old_dir)
        del test_repo
        shutil.rmtree(os.path.join(repo_path))

    def test_build_and_get_iqr(self):
        """
        Test `Project` method builds and extracts IQR flags.
        """
        # ensure we are starting from clean slate so that strace can
        # work its magic
        self.test_iqr_project.clean()
        output, rcode, stdout, stderr = self.test_iqr_project.build_and_get_iqr()
        if not os.path.exists("./test_logs"):
            os.makedirs("./test_logs")
        with open("./test_logs/test_build_and_get_iqr.txt", "wt") as f:
            print(f"rcode = {rcode}", file=f)
            print(f"\nstdout = \n {stdout}", file=f)
            print(f"\nstderr = \n {stderr}", file=f)
        self.assertEqual(output, self.test_iqr_project.serapi_options)
        actual_result = set()
        for match in re.finditer(r"(-R|-Q|-I) [^\s]+", output):
            actual_result.add(match.group())
        expected_result = {
            '-R vendor/array/src,Array',
            '-R src,SepLogic',
            '-R vendor/simple-classes/src,Classes',
            '-R vendor/tactical/src,Tactical'
        }
        self.assertEqual(actual_result, expected_result)
        self.assertEqual(rcode, 0)
        # build normally and compare output
        self.test_iqr_project.clean()
        _, expected_output, expected_err = self.test_iqr_project.build()
        # Test containment rather than equality because
        #   * submodules do not need to be re-initted, changing output
        #   * compilation order is not deterministic
        self.assertTrue(
            set(stdout.splitlines()).issuperset(expected_output.splitlines()))
        self.assertTrue(stderr.endswith(expected_err))


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    unittest.main()