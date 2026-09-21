"""Component test runner: real JinjaX components in Chromium, no backend.

Sits between Python unit tests and full E2E: the component under test is
rendered by the real JinjaX catalog with its colocated CSS/JS, served by an
ephemeral local server, and exercised in a real browser with controllable
timers, network and storage. No Docker, database or authentication.
"""
