# Material 3 token provenance

The M3 button-group values in `main.css` were transcribed from Google sources
during the third iteration, but nothing tied the numbers back to where they
came from — an update could silently diverge from the official values.

## What it does

- `src/frontend/design-tokens/material3/button-groups.yaml` is a versioned
  inventory of every M3 value the project uses: token name, value, the CSS
  custom property it maps to, and its provenance (repository, revision, file,
  selector — or the M3 web spec page where no generated file exists).
- `harness material check` verifies offline that each inventory token and the
  corresponding CSS custom property agree (dp maps to CSS px). It fails on a
  missing token or a value drift, never silently keeps the old value.
- Web values that have no M3 equivalent live in a separate `web_adaptations`
  section, each with an explicit rationale. The section is empty today: the 15%
  press expansion and the spring were removed with the stable-geometry decision
  (`docs/features-request/frontend.md`) and are recorded as comments in the
  inventory instead of as tokens.
- The same check runs as a unit test (`tests/unit/test_material_tokens.py`),
  so a CSS edit that forgets the inventory (or vice versa) fails the suite.

## How it is built

- The inventory is a Pydantic-validated YAML
  (`src/harness/commands/material.py`); `check()` parses `main.css` custom
  properties and compares them token by token.
- Provenance recorded: `material-components/material-components-android` tag
  `1.14.0` (commit `66c334b7946dabf33adfe1a2b7cad6bcaa4ea3ad`,
  `button_group_tokens.xml` and `tokens.xml`) and the Compose sources at
  androidx commit `3fac28c9daeb1322742860e9dc556efd83b340a0`
  (`ButtonGroupDefaults.ExpandedRatio`). Re-record the SHA/tag when the
  process is repeated — never just `master` or `androidx-main`.
## Limits

- `material sync` (fetching token values from the sources at a given revision)
  is a planned follow-up; today the inventory is updated by hand and `check`
  guards the agreement.
- Button groups, the switch and text fields are inventoried so far
  (`design-tokens/material3/*.yaml`); other M3 components can add their own
  YAML files there.
