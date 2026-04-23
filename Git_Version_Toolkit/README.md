# Git Version Toolkit

A reusable Git version management toolkit for any local Git project.

Current version: `1.0.0`

## Contents

```text
Git_Version_Toolkit/
|- docs/
|  |- Git工作流模板.md
|  `- Git版本管理与回退指南.md
|- scripts/
|  |- git-save.ps1
|  `- git-tag-release.ps1
|- templates/
|  `- PULL_REQUEST_TEMPLATE.md
|- release/
|- git-save.cmd
`- install.ps1
```

## What It Solves

- Quick save of current work
- Optional timestamped save points
- One-command local commit and push
- One-command annotated tag creation and push
- Reusable PR template for new repositories
- Reusable Git workflow docs for teams or personal projects

## Recommended Usage

Put `Git_Version_Toolkit` inside any Git project root:

```text
your-project/
|- Git_Version_Toolkit/
|- src/
|- docs/
`- README.md
```

Then use:

```cmd
Git_Version_Toolkit\git-save.cmd "save current progress"
```

Or:

```powershell
.\Git_Version_Toolkit\scripts\git-save.ps1 "save current progress" -Timestamp
.\Git_Version_Toolkit\scripts\git-tag-release.ps1 v0.1.0 "initial stable version"
```

## Install Script

The toolkit includes an installer:

```powershell
.\Git_Version_Toolkit\install.ps1 -TargetPath D:\path\to\your-project
```

If the target project already contains a `Git_Version_Toolkit` folder:

```powershell
.\Git_Version_Toolkit\install.ps1 -TargetPath D:\path\to\your-project -Overwrite
```

## Release Package

The `release/` directory contains a zip package that can be copied and extracted into other projects.

Current release package:

- `release/Git_Version_Toolkit_v1.0.0.zip`

## Main Files

- `scripts/git-save.ps1`: save current changes, commit, and optionally push
- `scripts/git-tag-release.ps1`: create and push annotated tags
- `git-save.cmd`: simple cmd wrapper for daily save
- `templates/PULL_REQUEST_TEMPLATE.md`: reusable PR template
- `docs/`: reusable Git workflow and rollback references
- `install.ps1`: installer for cross-project setup
