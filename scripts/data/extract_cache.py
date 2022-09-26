"""
Script to perform cache extraction.
"""
from prism.data.extract_cache import CacheExtractor
from prism.data.setup import create_default_switches
from prism.util.swim import AutoSwitchManager

if __name__ == "__main__":
    default_commits_path = "/workspace/pearls/cache/msp/repos"
    cache_dir = ""
    mds_file = ""
    create_default_switches(7)
    swim = AutoSwitchManager()
    project_root_path = ""
    log_dir = ""
    cache_extractor = CacheExtractor(
        cache_dir,
        mds_file,
        swim,
        default_commits_path)
    cache_extractor.run(project_root_path, log_dir, extract_nprocs=32)
