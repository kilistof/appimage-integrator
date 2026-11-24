# Security

## Trust boundary

The integrator executes an AppImage runtime with `--appimage-extract` under the
current user's permissions. Only use it with AppImages whose origin you trust.
The type-2 ELF marker is a format check, not a signature or authenticity check.
This program is not a sandbox, malware scanner, or application permission system.

Private extraction directories protect unrelated working-directory files from
normal cleanup. Metadata-link checks limit which extracted files the integrator
copies. Atomic writes protect individual replacements. These measures do not
restrict what a malicious AppImage runtime can do with your account.

Extraction is bounded by an elapsed-time limit, not a storage or memory quota.
Timeout and handled interruption terminate the extraction process group before
temporary cleanup. A process deliberately leaving that group, SIGKILL, or a
machine failure can prevent complete cleanup.

## Reporting a vulnerability

Report against the latest available version when possible. Include a minimal
reproduction, affected versions, expected boundary, and observed impact. Do not
use real private files or an executable third-party payload in the reproduction.

If the repository has private vulnerability reporting enabled, use **Security
→ Advisories → Report a vulnerability**. If that option is unavailable, open a
minimal issue asking the maintainer for a private reporting channel; leave
exploit details and private data out of the public issue.

Ordinary application compatibility and FUSE setup problems can use the normal
bug report form. Runtime behavior that is already outside the trust boundary
should be distinguished from an integrator defect.

Maintainer setup is described in [the publishing guide](docs/publishing.md).
