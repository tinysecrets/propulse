# AGPL compliance

The server-side project is licensed under AGPL-3.0-or-later. SDK packages are licensed separately under Apache-2.0 as described in the repository license files. Commercial licensing terms are documented in `LICENSE.commercial`; review them with qualified counsel before relying on them.

## Source disclosure

The API exposes `GET /source` for source-repository and license metadata. The response must reflect the repository URL and exact build commit for the deployed artifact.

## Release checklist

- Include the applicable license and copyright notices.
- Preserve source availability obligations for modified network-accessible AGPL software.
- Keep third-party dependency notices and SBOM artifacts with releases.
- Verify that SDK licensing boundaries match the contents actually distributed.
- Do not describe a release as compliant solely because a license file exists; verify distribution and deployment practices too.
