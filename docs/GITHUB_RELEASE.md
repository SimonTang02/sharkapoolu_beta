# GitHub release checklist

The repository is designed to publish code and placeholder configuration while
keeping all candidate-specific state local. Run these checks before creating a
GitHub remote:

```bash
make release-check
git status --short
git remote -v
```

Review every file that will enter the first public commit:

```bash
git ls-files --cached --others --exclude-standard
git diff --check
```

## Existing history

Do not push the current historical commits unchanged if they have ever contained
resumes, contact details, credentials, browser exports, databases, or generated
application artifacts. Removing a file in the current tree leaves its earlier
blob downloadable from Git history.

The safest publication path is a new repository made from the audited working
tree. Create it without copying the old `.git` directory:

```bash
make public-snapshot DEST=../26fall_intern_public
cd ../26fall_intern_public
make release-check
```

The destination must not already exist. The exporter copies only existing files
reported by `git ls-files --cached --others --exclude-standard`, initializes an
empty `main` branch, and creates no commit. Use a GitHub `noreply` address for
the first commit if the existing Git author email should remain private.

If preserving history is essential, rewrite it with `git filter-repo`, inspect
all rewritten commits, and rotate any credential that ever entered a commit.
History rewriting changes commit IDs and should be completed before a remote is
shared.

`make history-audit` provides an additional local check when the private profile
is available. It reports paths and marker labels rather than printing the
private values themselves.

## Repository settings

Before making the repository public:

1. Choose and add a license. Until a license is added, others have no general
   permission to copy, modify, or redistribute the code.
2. Add a short repository description and topics such as `job-search`,
   `resume`, `python`, and `browser-automation` only if they match the intended
   audience.
3. Keep GitHub Actions enabled so the public audit, tests, and shared config
   validation run on every push and pull request.
4. Never upload `private_data/`, `GPT_CONTEXT.md`, local browser profiles,
   cookies, SQLite databases, rendered PDFs, or local configuration overrides.
