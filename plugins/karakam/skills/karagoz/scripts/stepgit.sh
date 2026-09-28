#!/usr/bin/env bash
# Git operations on exactly one step's files_touched, run from the tree the
# step works in (the project root, or its worktree).
#
#   stepgit.sh commit "<message>" <path>...
#       Stage every change among <path>s — new, modified or deleted files — and
#       commit only those. Listed paths that don't exist and never did are
#       skipped (plain `git add` aborts on them). A failed commit is retried once
#       (signing and hooks can fail transiently); on failure nothing stays staged.
#   stepgit.sh land <worktree> <branch> "<message>" <path>...
#       Run from the project root for a parallel step that passed: commit
#       <path>s in <worktree>, merge <branch> into the current branch, then
#       remove the worktree and the branch. Each stage runs only if the one
#       before succeeded, so a failure never discards the step's work.
#       Exit 1: commit or merge failed, worktree kept. Exit 2: merge conflict,
#       merge aborted, worktree kept.
#   stepgit.sh revert <path>...
#       Put <path>s back exactly as they are in HEAD: undo edits, restore
#       deletions, remove files the step created. Plain `git checkout -- <paths>`
#       reverts nothing at all if one listed path is a new file.
set -uo pipefail

die() { echo "stepgit: $*" >&2; exit 1; }
self="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"

cmd=${1:-}; shift || true
case "$cmd" in
  commit)
    [ $# -ge 2 ] || die 'usage: stepgit.sh commit "<message>" <path>...'
    msg=$1; shift
    paths=()
    for p in "$@"; do
      if [ -e "$p" ] || git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
        paths+=("$p")
      fi
    done
    [ ${#paths[@]} -gt 0 ] || { echo "stepgit: none of the paths exist; nothing to commit"; exit 0; }
    git add -A -- "${paths[@]}" || die "git add failed"
    if git diff --cached --quiet -- "${paths[@]}"; then
      echo "stepgit: no changes in these paths; nothing to commit"; exit 0
    fi
    if ! git commit -q -m "$msg" -- "${paths[@]}" && \
       ! { sleep 3; git commit -q -m "$msg" -- "${paths[@]}"; }; then
      git reset -q -- "${paths[@]}" 2>/dev/null
      die "git commit failed (hook, identity, signing or permissions) — the step is not checkpointed"
    fi
    echo "stepgit: committed $(git rev-parse --short HEAD) — $msg"
    ;;
  land)
    [ $# -ge 4 ] || die 'usage: stepgit.sh land <worktree> <branch> "<message>" <path>...'
    wt=$1 br=$2 msg=$3; shift 3
    [ -d "$wt" ] || die "no worktree at $wt"
    ( cd "$wt" && bash "$self" commit "$msg" "$@" ) \
      || die "commit in $wt failed — worktree kept, nothing merged"
    merged=0
    for try in 1 2; do
      if git merge -q --no-ff "$br" -m "$msg"; then merged=1; break; fi
      if [ -n "$(git diff --name-only --diff-filter=U)" ]; then
        git merge --abort
        echo "stepgit: merge conflict with $br — merge aborted, worktree kept" >&2
        exit 2
      fi
      git merge --abort 2>/dev/null || true
      sleep 3
    done
    [ $merged = 1 ] || die "merging $br failed — worktree kept, its commit is on $br"
    git worktree remove --force "$wt" || die "merged, but removing $wt failed"
    git branch -q -d "$br" || die "merged, but deleting branch $br failed"
    echo "stepgit: landed $br — $msg"
    ;;
  revert)
    [ $# -ge 1 ] || die "usage: stepgit.sh revert <path>..."
    git reset -q -- "$@" 2>/dev/null || true            # unstage whatever is staged
    git ls-tree -r -z --name-only HEAD -- "$@" | xargs -0 -r git checkout HEAD -- \
      || die "restoring tracked files failed"
    git clean -fq -- "$@" || die "removing new files failed"
    echo "stepgit: reverted $# path(s) to HEAD"
    ;;
  *) die 'usage: stepgit.sh commit|land|revert … (see the header)' ;;
esac
