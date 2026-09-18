# Operations Log

## 2026-09-18 - Publish public GitHub artifact

- Task: create a public GitHub artifact repository and register its URL in
  HotCRP submission #27.
- Tools: GitHub CLI 2.101.0, GitHub device login, in-app browser, git.
- Operations:
  - Revoked the exposed GitHub token; no replacement token was written to the
    repository or chat.
  - Created `https://github.com/ListenJ/chia-repo-audit` as a public
    repository.
  - Pushed local `main` commit `6c959c109a01972958e3ffc2c3b1117d9b2f5bed`
    unchanged to GitHub.
  - Filled the HotCRP `Open-source artifact URL` and saved submission #27 as
    a draft.
- Verification:
  - Anonymous GitHub API reports `visibility=public` and
    `default_branch=main`.
  - `git ls-remote github refs/heads/main` matches local `main`.
  - HotCRP reports `Updated submission (changed Open-source artifact URL)`.
- Deviation: AGENTS rule 3 names `agent/Axiom` as the normal target. This task
  intentionally used the public artifact repository `ListenJ/chia-repo-audit`
  per the user's submission request. No force push or history rewrite was
  performed.
- Commit: `0712041`
