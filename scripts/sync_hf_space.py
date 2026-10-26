"""Mirror the tested GitHub source to the Hugging Face Space (run by CI on a release tag).

Uploads every git-tracked file and deletes application files the release no longer
contains. Requires HF_TOKEN with write access to the Space only.
"""

import os
import subprocess
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

REPO_ID = "lichao622/reachy_mini_ha_voice"
ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def main():
    tag = sys.argv[1]
    sha = git("rev-parse", "HEAD").strip()
    if git("status", "--porcelain").strip():
        raise SystemExit("Working tree is not clean; refusing to publish")
    files = [name for name in git("ls-files", "-z").split("\0") if name]
    tracked = set(files)
    api = HfApi(token=os.environ["HF_TOKEN"])
    operations = [CommitOperationAdd(path_in_repo=name, path_or_fileobj=str(ROOT / name))
                  for name in files]
    for name in api.list_repo_files(REPO_ID, repo_type="space"):
        if name.startswith("reachy_mini_ha_voice/") and name not in tracked:
            operations.append(CommitOperationDelete(path_in_repo=name))
    commit = api.create_commit(REPO_ID, repo_type="space", operations=operations,
                               commit_message=f"Sync tested GitHub source {sha} ({tag})")
    print(commit.commit_url)


if __name__ == "__main__":
    main()
