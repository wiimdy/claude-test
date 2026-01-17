# /commit Command

Commit changes to the repository with a well-crafted commit message.

## Instructions

1. Run `git status` to see all changes (staged and unstaged)
2. Run `git diff` to see the actual changes
3. Run `git log --oneline -5` to see recent commit message style
4. Stage all relevant changes with `git add`
5. Write a clear, concise commit message that:
   - Uses conventional commit format (feat:, fix:, docs:, refactor:, test:, chore:)
   - Summarizes the "why" not just the "what"
   - Is 1-2 sentences max
6. Create the commit with the message ending with:
   ```
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```
7. Run `git status` to confirm the commit succeeded

## Rules

- Do NOT commit files that may contain secrets (.env, credentials, etc.)
- Do NOT use `git commit --amend` unless explicitly requested
- Do NOT push automatically - only commit
- If there are no changes, inform the user
