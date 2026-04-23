# Git工作流模板

## 分支命名模板

- `feature/功能名`
- `fix/问题名`
- `hotfix/问题名`

## 提交信息模板

```text
feat: 新增xxx
fix: 修复xxx
docs: 更新xxx
refactor: 重构xxx
test: 补充xxx测试
chore: 清理或配置xxx
```

## 每天开始开发

```powershell
git checkout main
git pull origin main
git checkout -b feature/任务名
```

## 开发过程中的保存

```powershell
git add .
git commit -m "feat: 当前阶段说明"
git push origin 当前分支名
```

## 一键保存

```cmd
Git_Version_Toolkit\git-save.cmd "保存当前开发进度"
```

```powershell
.\Git_Version_Toolkit\scripts\git-save.ps1 "保存当前开发进度" -Timestamp
```

## 打标签

```powershell
.\Git_Version_Toolkit\scripts\git-tag-release.ps1 v0.1.0 "初始稳定版本"
```

## 常用回退命令

```powershell
git log --oneline --decorate --graph --max-count=10
git restore 文件路径
git reset --soft HEAD~1
git checkout -b rollback-check 提交号
```
