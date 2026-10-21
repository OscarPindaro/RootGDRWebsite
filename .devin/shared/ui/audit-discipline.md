# Design audit procedure

Use the same severity scale for code and screenshot reviews:

- Critical: an accessibility blocker or confirmed WCAG 2.2 AA failure.
- High: a semantic or structural problem that misleads or excludes a user.
- Medium: a consistency problem that materially affects use.

Report evidence as confirmed, approximate or structural. For estimates or
source-based conclusions, name the browser check, interaction or measurement
needed to confirm the issue.

Each finding needs a location or image region, defect, impact and proposed
correction. Accessibility findings also cite the relevant WCAG criterion.
Group repeated causes with up to three examples and the remaining count.
Order findings by severity.

State evidence limits. Code alone cannot establish final rendering or
interaction; screenshots cannot prove semantics, keyboard behavior, accessible
names, hidden states or responsiveness across viewports.

Audits never edit. Repairs require implementation authority and appropriate
verification. Suggest at most one additional evidence source that would resolve
a specific gap.
