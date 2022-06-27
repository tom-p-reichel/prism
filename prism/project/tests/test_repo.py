"""
Test module for prism.project.repo module.
"""
import os
import unittest

from git import Repo

from prism.project.repo import CommitIterator, CommitMarchStrategy

TEST_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(TEST_DIR)
PRISM_DIR = os.path.dirname(PROJECT_DIR)
REPO_DIR = os.path.dirname(PRISM_DIR)

FIRST_HASH = "1aa5cfb2240df880f6c1d457f66c4b0a01e0a1aa"
SECOND_HASH = "29a790c002f8e797a01fb87b64fc2db85d147e25"
THIRD_HASH = "d689b50282393a74d43ea811ba232e5f2206aa0e"
FOURTH_HASH = "248a03133252d6a3063dc61e2ee73af228cc58aa"
FIFTH_HASH = "7219a28b131dd91aafc9daf67ef2c295ecbff910"

HASHES = [FIRST_HASH, SECOND_HASH, THIRD_HASH, FOURTH_HASH, FIFTH_HASH]


class TestCommitIter(unittest.TestCase):
    """
    Class for testing CommitIter class.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up class for testing CommitIter class.
        """

    def test_iterator_newest_first(self):
        """
        Test iterator basic functionality.
        """
        repo = Repo(REPO_DIR)
        counter = 0
        hashes = [THIRD_HASH, FOURTH_HASH, FIFTH_HASH]
        for commit in CommitIterator(repo, THIRD_HASH):
            if counter == 3:
                break
            print(counter, commit.hexsha, flush=True)
            self.assertTrue(commit.hexsha == hashes[counter])
            counter += 1

    def test_iterator_oldest_first(self):
        """
        Test iterator oldest first functionality.
        """
        repo = Repo(REPO_DIR)
        counter = 0
        hashes = [THIRD_HASH, SECOND_HASH, FIRST_HASH, FOURTH_HASH, FIFTH_HASH]
        for commit in CommitIterator(repo,
                                     THIRD_HASH,
                                     CommitMarchStrategy.OLD_MARCH_FIRST):
            if counter == 5:
                break
            print(counter, commit.hexsha, flush=True)
            self.assertTrue(commit.hexsha == hashes[counter])
            counter += 1

    def test_iterator_curlicue_new(self):
        """
        Test iterator curlicue new functionality.
        """
        repo = Repo(REPO_DIR)
        counter = 0
        hashes = [THIRD_HASH, SECOND_HASH, FOURTH_HASH, FIRST_HASH, FIFTH_HASH]
        for commit in CommitIterator(repo,
                                     THIRD_HASH,
                                     CommitMarchStrategy.CURLICUE_NEW):
            if counter == 5:
                break
            print(counter, commit.hexsha, flush=True)
            self.assertTrue(commit.hexsha == hashes[counter])
            counter += 1

    def test_iterator_curlicue_old(self):
        """
        Test iterator curlicue old functionality.
        """
        repo = Repo(REPO_DIR)
        counter = 0
        hashes = [THIRD_HASH, FOURTH_HASH, SECOND_HASH, FIFTH_HASH, FIRST_HASH]
        for commit in CommitIterator(repo,
                                     THIRD_HASH,
                                     CommitMarchStrategy.CURLICUE_OLD):
            if counter == 5:
                break
            print(counter, commit.hexsha, flush=True)
            self.assertTrue(commit.hexsha == hashes[counter])
            counter += 1


if __name__ == "__main__":
    unittest.main()
