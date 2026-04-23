# Git Version Toolkit

一套可复用的 Git 版本管理工具链，适用于任意本地 Git 项目。

## 目录结构

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
`- git-save.cmd
```

## 适用场景

- 日常开发时快速保存当前代码
- 每天下班前一键提交并推送
- 给稳定版本打 tag 并推送
- 为新项目提供统一的 PR 模板和 Git 工作流规范

## 放置方式

推荐把整个文件夹直接放到任意 Git 项目的根目录下，例如：

```text
your-project/
|- Git_Version_Toolkit/
|- src/
|- docs/
`- README.md
```

脚本会自动寻找当前所在的 Git 仓库根目录，不依赖固定项目名。

## 最常用命令

在项目根目录执行：

```cmd
Git_Version_Toolkit\git-save.cmd "保存当前开发进度"
```

带时间戳保存：

```powershell
.\Git_Version_Toolkit\scripts\git-save.ps1 "保存当前开发进度" -Timestamp
```

只做本地保存点：

```powershell
.\Git_Version_Toolkit\scripts\git-save.ps1 "本地保存点" -SkipPush
```

创建并推送版本标签：

```powershell
.\Git_Version_Toolkit\scripts\git-tag-release.ps1 v0.1.0 "初始稳定版本"
```

## 查看帮助

```powershell
Get-Help .\Git_Version_Toolkit\scripts\git-save.ps1 -Full
Get-Help .\Git_Version_Toolkit\scripts\git-tag-release.ps1 -Full
```

## 配套文件说明

- `docs/`：Git 使用规范和工作流模板
- `scripts/`：可执行的 PowerShell 脚本
- `templates/`：可复制到项目根目录 `.github/` 下的模板文件
- `git-save.cmd`：适合双击或在 `cmd` 中直接调用的简化入口
