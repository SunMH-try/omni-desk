# Git版本管理与回退指南

## 目标

这套工具链的目标有 4 个：

1. 开发中随时可保存
2. 误删误改后可以快速找回
3. 每个阶段有明确版本
4. 本地和远程始终可恢复

## 分支建议

- `main`：稳定版本
- `feature/*`：新功能开发
- `fix/*`：问题修复
- `hotfix/*`：紧急修复

建议一个任务一个分支，不在 `main` 上长期直接开发。

## 日常流程

开始新任务：

```powershell
git checkout main
git pull origin main
git checkout -b feature/任务名
```

开发中保存：

```powershell
git add .
git commit -m "feat: 当前阶段说明"
git push origin 当前分支名
```

合并回主分支：

```powershell
git checkout main
git pull origin main
git merge 当前分支名
git push origin main
```

## 提交规范

推荐前缀：

- `feat:`
- `fix:`
- `docs:`
- `refactor:`
- `test:`
- `chore:`

## 打版本标签

```powershell
git tag -a v0.1.0 -m "版本说明"
git push origin v0.1.0
```

建议在“阶段可运行且值得回退”的时点打 tag。

## 回退建议

恢复单个文件：

```powershell
git checkout 提交号 -- 文件路径
```

基于旧版本新建恢复分支：

```powershell
git checkout -b rollback-check 提交号
```

撤销最近一次提交但保留代码：

```powershell
git reset --soft HEAD~1
```

## 高风险命令

除非非常确认，否则不要轻易使用：

- `git reset --hard`
- `git checkout -- .`
- `git clean -fd`
- `git push --force`

## 最低执行要求

- 开工前 `pull`
- 新任务开分支
- 每 30 分钟到 1 小时至少提交一次
- 每天下班前至少 push 一次
- 每个稳定阶段打一个 tag
