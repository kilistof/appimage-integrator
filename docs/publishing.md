# Publish this directory on GitHub

This source directory is ready to become a repository named
`appimage-integrator`. It contains the executable, documentation, tests, license,
and hidden GitHub configuration files. Publish the directory's contents as the
repository root; a ZIP uploaded as one repository file would hide the source
and prevent the workflow from being recognized.

## Prepare the local Git repository

Open a terminal in this directory. The distribution archive intentionally does
not include existing Git history, author identity settings, or a remote URL.

```bash
git init -b main
git add .
git update-index --chmod=+x appimage-integrator
git status --short
git commit -m "Prepare AppImage Integrator 2.1.0"
```

Use your own Git author identity if Git asks for one. The executable-bit command
ensures that the published entry point remains executable even if an archive
manager did not restore Unix permissions. `git add .` includes `.github`,
`.gitignore`, `.gitattributes`, and `.editorconfig`.

The project currently uses the [MIT license](../LICENSE) with contributor-level
copyright attribution. It permits redistribution and modification while
requiring the license and copyright notices to be retained. If you intend a
different license or attribution, make that deliberate edit before publishing.

## Publish with GitHub CLI

Install GitHub CLI (`gh`) and sign into the account that should own the project
if you have not already done so:

```bash
gh auth login
```

Run the following when ready to make the source public. It creates the remote
repository, adds `origin`, and pushes the local commit:

```bash
gh repo create appimage-integrator \
  --public \
  --source=. \
  --remote=origin \
  --description "User-local desktop integration for trusted type-2 AppImages" \
  --push
```

The name is relative to your authenticated account. If that name already exists,
use another name or follow the existing-repository route below. No credentials
belong in the source directory.

## Publish through GitHub's website and Git

Alternatively, create a new public repository in the GitHub web interface.
Keep it empty: the README, `.gitignore`, and license already exist locally, so
do not ask GitHub to generate additional versions of those files.

Copy the repository's SSH or HTTPS URL from its Quick Setup page. Use it with
`git remote add origin`, then push the `main` branch:

```bash
git remote add origin "PASTE_YOUR_REPOSITORY_URL_HERE"
git push -u origin main
```

Replace the quoted placeholder with the URL you copied. For an existing remote
with commits, clone it first and copy these files into that working tree;
reconcile its existing README, license, and history normally. Do not force-push
an unrelated history.

## After the first push

Open the **Actions** tab and inspect the `CI` workflow. It is configured to run
checks for pushes and pull requests on Ubuntu 22.04 and 24.04. The local
validation record does not claim that the hosted workflow has already run.

To support the private-reporting route described in [Security](../SECURITY.md),
enable **Private vulnerability reporting** in the repository's security
settings. This is a repository setting; committing `SECURITY.md` does not
enable it automatically.

When you choose to publish a tagged release, tag the tested commit and push the
tag, then create the release in GitHub. Version `2.1.0` is the prepared source
version; no tag or hosted release is created by extracting this directory.

## Official references

- [GitHub CLI: gh repo create](https://cli.github.com/manual/gh_repo_create)
- [GitHub: create a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [GitHub: private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)
- [MIT license summary](https://choosealicense.com/licenses/mit/)
