# Security Policy

DelegationHQ is early-stage software. It should not be trusted with secrets,
privileged automation, or production write access without careful review.

## Supported Versions

The project is pre-release. Security fixes target the active `main` branch until
release versioning is formalized.

## Reporting A Vulnerability

Please do not open public issues for sensitive vulnerabilities.

Preferred reporting path:

1. Use GitHub private vulnerability reporting if it is enabled.
2. If private reporting is not available, contact the maintainer through GitHub.
3. Include reproduction steps, impact, affected files, and any suggested fix.

A dedicated security email should be created before the first broad public
launch.

## Security Principles

- No live writes by default.
- No hidden network execution.
- No secret logging.
- Approval gates for risky actions.
- Ledger evidence for executed work.
- Clear separation between dry-run planning and apply mode.
