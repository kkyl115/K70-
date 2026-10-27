# Vermeer Ultimate Kernel + BootGuard

目标设备：Redmi K70 / `vermeer` / SM8550 (Kalama) / HyperOS `OS3.0.302.0.WNKCNXM` / Android 16
当前运行内核：`5.15.178-android13-8-g362d545d31a5`（GKI，KMI 系列 `android13-5.15`）
工作区根目录：`/storage/emulated/0/Download/vermeer-ultimate-kernel`

## 0. 先说清楚：本仓库现在是什么、不是什么

| 项目 | 实际情况 |
|---|---|
| 环境实测证据 | ✅ 真实采集，见 `evidence/noroot_20261027_221752/` |
| BootGuard A 槽备份核验 | ✅ 5/5 分区 SHA-256 全 PASS，真实执行过 |
| BootGuard 只读预检脚本 | ✅ 已写成，可直接在本机运行 |
| 内核源码构建 | ❌ 未进行。本机是 aarch64，GKI 的 Kleaf/Bazel + AOSP 预编译 clang 只有 x86_64 版本 |
| 内核 Image / 刷机包 | ❌ 不存在，也不会伪造 |
| VAS 调度器内核代码 | 💭 仅设计。改 `kernel/sched/` 会破坏 GKI KMI 白名单，且无法在本机编译验证 |
| 三档调度配置 | 🧪 调参层已写（sysfs/属性），需 root 才能应用与验证 |
| 真机启动验证 | ❌ 不可能由 AI 完成，必须你本人操作 |

**本仓库不含任何"编译成功""启动通过"的伪造记录。** 每一项状态都可回溯到 `evidence/`。

## 1. 目录

```
vermeer-ultimate-kernel/
├── sources/          # 上游源码引用清单（不是源码本身，见 sources/SOURCES.md）
├── toolchains/       # 工具链锁定清单
├── patches/          # sukisu / susfs / kpm / memory / scheduler-vas / networking / security
├── configs/          # baseline / balanced / performance / efficiency
├── bootguard/        # preflight / backup / recovery / rollback
├── scripts/          # 证据采集、构建、应用配置
├── tests/            # 门禁用例
├── evidence/         # 实测证据（只增不改）
├── docs/             # 环境实测报告、根因分析、操作指南
├── build/            # 构建配置与 Actions workflow
└── release/          # 产物目录（当前为空，没有产物就是没有）
```

## 2. 立即可以跑的两件事

### 2.1 无 root 只读证据采集（已验证可跑）

```bash
bash /storage/emulated/0/Download/vermeer-ultimate-kernel/scripts/collect_evidence_noroot.sh
```

输出 9 个文件到 `evidence/noroot_<时间戳>/`，不申请 root，不写分区。

### 2.2 BootGuard 只读预检（不刷机、不切槽）

```bash
bash /storage/emulated/0/Download/vermeer-ultimate-kernel/bootguard/preflight/preflight_check.sh
```

只做校验与报告，任何写操作都需要额外的 `--allow-write` 参数与二次确认，当前版本**没有任何写路径**。

## 3. 当前唯一的硬阻塞：Termux 拿不到 root

实测（`evidence/noroot_20261027_221752/07_root_facts.txt`）：

- `/debug_ramdisk/su`、`/sbin/su`、`/system/bin/su`、`/system/xbin/su`、`/data/adb/ksu/bin/su`、`/data/adb/magisk/su` **全部 MISS**
- `/proc/config.gz`、`/proc/modules`、`/proc/cmdline`、`/proc/kallsyms`、`/data/adb` **全部拒读**
- `ls /sys/module` **Permission denied**（所以无法判断 kernelsu 模块是否加载 —— 这一点必须诚实：不是"没有"，是"看不到"）
- `id` → `uid=10369(u0_a369) ... context=u:r:untrusted_app_27:s0`

结论：**Termux 进程没有任何 root 通道**。若 SukiSU 管理器侧确实显示工作中，问题在于 `com.termux` 未被授权或 su 未在该命名空间暴露，而不是"你没 root"。

绕过办法见 `docs/01_根因分析与阻塞清单.md` 第 3 节：`scripts/collect_evidence_root.sh` 设计为在 **SukiSU 管理器自带的 root 终端**里运行，输出写 `/sdcard`。

## 4. 纪律

1. 不刷机、不切槽、不碰 A 槽、不关 AVB/SELinux。
2. 补丁应用成功 ≠ 编译成功 ≠ 能开机。三者分开记。
3. 未经真机验证的内核永远不标记为 stable。
4. 没有 root 证据（config / Module.symvers / KMI 符号表）之前，不产出可刷写镜像。
