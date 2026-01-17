# /push Command

Push commits to the remote repository.

## Instructions

1. Run `git status` to check current branch and sync status
2. Run `git log origin/$(git branch --show-current)..HEAD --oneline` to see commits that will be pushed
3. If there are commits to push:
   - Show the user what will be pushed
   - Run `git push` (or `git push -u origin <branch>` if no upstream is set)
4. Run `git status` to confirm push succeeded

## Rules

- NEVER use `git push --force` unless explicitly requested
- NEVER push to main/master without user confirmation
- If there are uncommitted changes, warn the user first
- If no commits to push, inform the user
