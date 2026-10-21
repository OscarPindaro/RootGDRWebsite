# Changelog release

Use this procedure only for a manually maintained changelog. If the repository
uses Towncrier or another generator, return to the main skill and follow its
tooling path. Repository version and release approvals take precedence.

Edit `CHANGELOG.md` only. Load the SemVer table from `writing-guidelines.md` and use the main skill's pre-flight.

1. **Validate.** `[Unreleased]` must contain an entry. Otherwise stop and suggest `add` or `from-commits`. The previous version is the first `## [X.Y.Z]` heading, or `0.0.0`; changelog order, not tags or numeric maximum, is authoritative. Note whether version compare-link footers exist.
2. **Choose the version.** Follow the repository's version policy. Where it permits a recommendation, explain the SemVer implication from the table and ask for the version in plain prose. Never select or apply a bump without the required approval.
3. **Cut the release.** Rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` using today's date, and insert a fresh empty `## [Unreleased]` above it. Do not touch older releases.
4. **Maintain existing footers only.** If compare-link footers exist, copy their host-specific shape, add the new version line, and repoint `[Unreleased]` from the new version. If none exist, add none.
5. **Report, do not run, follow-up commands.** If version files such as `package.json`, `pyproject.toml`, `plugin.json`, or `Cargo.toml` exist, say they must be updated first. Then print:

```bash
git add CHANGELOG.md   # plus version files changed by the user
# create the release commit with /commit
git tag vX.Y.Z
git push && git push origin vX.Y.Z
```

State that this skill ran none of those commands.
