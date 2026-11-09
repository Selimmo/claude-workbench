# Releasing plan-review

Installs come from release zips, never from `main`: Claude Code copies a plugin into its cache and only fetches it again when its version changes. Only the owner releases. Nothing goes to PyPI.

```bash
cd plugins/plan-review
./release.sh patch     # or ./release.sh 0.3.0
```

`release.sh` runs on an up-to-date, clean `main`. It sets the version in `plugin.json`, `pyproject.toml` and `uv.lock`, commits, tags `plan-review--v<version>` and pushes both together. `patch` bumps the last release, or releases the version a pull request already set; any version must be newer than the last release. Before releasing, move the `Unreleased` notes in [CHANGELOG.md](CHANGELOG.md) under the new version.

The tag starts `plan-review-release.yml`:

1. **build** (read-only token): runs `check.sh`, which builds the viewer page, and zips the plugin with `scripts/package.sh` (the files in `scripts/shipped-paths`, the built page and `LICENSE`, plugin root at the top). The built page ships only in the zip: `static/` stays gitignored.
2. **publish**: attaches `plan-review-<version>.zip` and `plan_review-<version>-py3-none-any.whl` (built after `check.sh`; Codex installs from it) to the GitHub release, then runs `scripts/link-release.sh`. If the repo is **public**, it commits the marketplace entry (`archive` source: url, sha256, version) to `main`. If it is **private** (a fork, say), the release is a test release: the log says so and `main` is left alone, because the zip's URL is a 404 for anyone without access.

## Version guard

CI fails when anything that ends up in the zip changed since the release of the version in `plugin.json`: the shipped files, the viewer page's sources (`scripts/build-inputs`, without its tests) or `LICENSE`. The first pull request after a release that touches one bumps the version with `scripts/set-version.sh <next>`; `release.sh patch` then releases that version without another commit.

## When a release fails

Use **Re-run failed jobs**: it reuses the zip `build` already made, the release is reused and the zip replaced (`--clobber`), and an entry already linked is left as it is. Avoid **Re-run all jobs** once `main` points at the zip: `build` makes a new zip with a different sha256 and replaces the asset, so installs fail on the sha256 pin until `publish` commits the new one.

If `check.sh` fails, the tag already exists and the version guard treats it as released: fix the problem on `main` and release the next patch. To drop the broken tag too, run `git push origin :refs/tags/plan-review--v<version>` and `git tag -d plan-review--v<version>`.

If `release.sh`'s push is refused (it is atomic, so neither `main` nor the tag reaches origin), remove the local commit and tag with `git reset --hard origin/main && git tag -d plan-review--v<version>`, then pull and run it again. Protecting `main` on GitHub would block both `release.sh`'s and the workflow's pushes.

## Proving install and upgrade in a throwaway config

`scripts/prove-release.sh` installs and upgrades the latest release in a throwaway Claude Code config (your own `~/.claude` is not touched). It works on private repos too, which is how 0.1.1 and 0.1.2 were proven before the repo went public ([#34](https://github.com/Selimmo/claude-workbench/issues/34)).

After one release run `scripts/prove-release.sh install ~/tmp/proof`; after the next, `scripts/prove-release.sh upgrade ~/tmp/proof`. A private asset's download link takes no token, so the script builds a local copy of the marketplace whose entry downloads the latest release's zip through the GitHub API with your `gh` login, sent by a `headersHelper` (Claude Code asks you to accept it). It also prints the asset's download count before and after, and the versions now in the throwaway cache. When done, delete the folder (`rm -rf ~/tmp/proof`): it holds a whole throwaway Claude Code config, the zips and a Python environment.

## Proving the Codex install and upgrade

`scripts/prove-codex-release.sh ~/tmp/codex-proof` installs the release wheels in a throwaway home (`HOME`, `CODEX_HOME` and the uv tool folders are all inside the folder), checks the version, the ship skill and the four agents, and does not start Codex. With two releases that carry a wheel it installs the older one and runs its own `plan-review upgrade`; with one it proves the install and says the upgrade needs a second release. The first release with a wheel has nothing to upgrade from, so prove the upgrade after the next one.

`link-release.sh` also rewrites the `uv tool install` line in the root README to the new wheel, in the same commit as the marketplace entry.

## Download counts

Each release asset's download count is its install and update count (downloads through the API asset URL, as `prove-release.sh` uses, are not counted):

```bash
gh api repos/Selimmo/claude-workbench/releases --jq '.[] | {tag_name, downloads: [.assets[].download_count]}'
```
