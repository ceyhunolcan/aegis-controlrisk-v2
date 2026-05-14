# Security policy

## Supported versions

Only the latest minor release receives security fixes. v2.x is current.

| Version | Supported |
|---------|-----------|
| 2.x     | ✅        |
| < 2.0   | ❌        |

## Reporting a vulnerability

If you've found a security issue, please **do not open a public GitHub
issue**. Email the contact listed in [COMMERCIAL.md](COMMERCIAL.md)
with:

- A description of the issue
- Steps to reproduce
- What an attacker could do with it
- Your suggested fix, if any

Response within two business days. Coordinated disclosure preferred:
I'll work with you on a fix timeline before any public posting.

## What counts as a security issue

- Authentication or authorization bypass in the workspace model
- Path traversal in snapshot / cache / workspace storage
- Code execution via crafted input to the pipeline
- Denial-of-service via specific inputs (infinite loop, runaway memory)
- Exfiltration of `_provenance` or audit data across workspaces
- Any vulnerability in dependencies that affects this codebase

## What's *not* a security issue

- The synthetic dataset producing "wrong" risk scores — it's
  intentionally fictional
- Outputs disagreeing with your expert judgment — open an issue,
  not a security report
- Streamlit dashboard reflecting input you typed into the URL —
  the dashboard is not multi-tenant and isn't intended for
  unauthenticated public exposure
