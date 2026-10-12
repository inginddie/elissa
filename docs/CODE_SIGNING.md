# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).

## What is signed

Only binaries built from this repository's source code are signed: the Elissa installer (`Elissa_x.y.z_x64-setup.exe`)
and the programs it installs. They are built by GitHub Actions on GitHub-hosted runners with the public workflow in
[`.github/workflows/release.yml`](../.github/workflows/release.yml). Third-party components bundled with Elissa (for
example the Python runtime and libraries, or downloaded models) are not signed with this certificate.

## Team roles

| Role | Members |
|---|---|
| Committers and reviewers | [Diego Bustos (@inginddie)](https://github.com/inginddie) |
| Approvers | [Diego Bustos (@inginddie)](https://github.com/inginddie) |

- Committers can change the code.
- Changes from anyone else arrive as pull requests, and a reviewer must approve them before they are merged.
- An approver manually approves every signing request.
- Every member uses multi-factor authentication on GitHub and SignPath.

The current list of people with write access is [the repository's collaborators](https://github.com/inginddie/elissa/graphs/contributors).

## Privacy

Elissa sends data only to the services you choose, and only for the features you use: your AI provider, your
speech service and the voice service. The [privacy policy](../PRIVACY.md) lists each one and how to turn it off. The
installer shows a summary before installing.
