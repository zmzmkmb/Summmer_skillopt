# ACL 2027 新电脑恢复手册

本仓库可以恢复代码、配置、测试、论文状态和小型审计产物。原电脑上的虚拟环境、`.env`、ALFWorld 数据集和大型运行结果没有放进 Git，需要单独迁移。

## 1. 克隆固定分支

```powershell
git clone --branch codex/acl2027-foundation https://github.com/zmzmkmb/Summmer_skillopt.git
cd Summmer_skillopt
```

不要直接从 `master` 开始；ACL 2027 当前工作在 `codex/acl2027-foundation`。

## 2. Windows 环境准备

安装以下软件：

- Git for Windows
- Python 3.11 或 3.12
- WSL2 + Ubuntu

在 PowerShell 中运行：

```powershell
.\scripts\bootstrap_acl2027.ps1 -Install
```

这会创建 `.venv-acl2027`、安装核心/测试依赖、复制 `.env.example` 为本地 `.env`，并运行实验状态校验。它不会启动任何实验。

## 3. WSL/ALFWorld 环境

把 ALFWorld 数据放在 WSL 可访问的位置。推荐：

```bash
mkdir -p "$HOME/ALFWORLD_DATA"
export ALFWORLD_DATA="$HOME/ALFWORLD_DATA"
```

数据目录至少应包含：

```text
$ALFWORLD_DATA/json_2.1.1/
```

在 WSL 中进入仓库并运行：

```bash
bash scripts/bootstrap_acl2027_wsl.sh
```

如果仓库位于 Windows 磁盘，WSL 路径通常类似 `/mnt/e/桌面/暑期实训/SummerSkillOpt`；不要把旧电脑中的 `C:/Users/CMCC/ALFWORLD_DATA` 硬编码到新电脑配置中。

## 4. API 配置

`.env` 只保存在本机，不能提交：

```powershell
notepad .env
```

从旧电脑迁移真实 API key 时，只复制变量值，不复制整个旧 `.env` 中与机器路径相关的内容。仓库已经忽略 `.env`、`.venv-*`、`graphify-out` 和运行中间文件。

## 5. 恢复检查

```bash
python scripts/acl2027_experiment_handoff.py validate
python scripts/acl2027_experiment_handoff.py status
python -m pytest -q -p no:cacheprovider \
  tests/test_acl2027_experiment_handoff.py \
  tests/test_acl2027_tracegraph_tg8_observable_subgoal_selector_v3.py \
  tests/test_acl2027_tracegraph_tg9_selector_v1.py
```

如果这些命令通过，说明代码、当前实验状态和 selector 逻辑已经恢复。先不要运行任何 `authorized` runner。

## 6. 大型结果的迁移

普通 Git 克隆不会包含约 1 GB 的旧运行结果，尤其是：

- `artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1/result.json`
- `artifacts/acl2027_tracegraph_tg9_factorial_v1/independent_20260918_v4/result.json`
- `artifacts/acl2027_tracegraph_tg7_progress_memory_runner_v1/result_authorized_wsl_20260909.json`

这些结果应通过移动硬盘、局域网或 Git LFS/对象存储迁移，并在新电脑上按原路径恢复。恢复后用 SHA-256 对照 `paper/acl2027/experiment_state.json` 和 `CROSS_CONVERSATION_PROTOCOL.md` 中记录的指纹。

## 7. 实验边界

当前状态文件显示 TG8/TG9 的旧授权已经消耗或关闭。新电脑准备好不等于获得新的实验授权。任何新运行都必须：

1. 创建新版本的 config、runner、schedule 和输出目录；
2. 先通过零网络 preflight；
3. 获得绑定这些文件 SHA-256 的一次性明确授权；
4. 再启动 runner。

恢复脚本只负责环境和只读校验，永远不会替你越过这四道门。
