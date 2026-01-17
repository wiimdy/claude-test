# /pr Command

Create a pull request on GitHub.

## Instructions

1. Run `git status` to check current state
2. Run `git branch --show-current` to get current branch name
3. Run `git log main..HEAD --oneline` to see all commits in this branch
4. Run `git diff main...HEAD` to see all changes
5. If there are unpushed commits, push them first with `git push -u origin <branch>`
6. Create the PR using:
   ```bash
   gh pr create --title "<title>" --body "$(cat <<'EOF'
   ## Summary
   <bullet points describing the changes>

   ## Test plan
   <how to test these changes>

   ---
   Generated with Claude Code
   EOF
   )"
   ```
7. Return the PR URL to the user

## Rules

- Analyze ALL commits in the branch, not just the latest one
- Write a clear, descriptive title
- Include a summary of what changed and why
- Do NOT create a PR if already on main/master branch
- If a PR already exists for this branch, show its URL instead
