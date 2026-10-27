# 项目状态看板

更新时间：2026-10-27（全部状态基于本机实测，不基于推测）

状态图例：✅ 有源码/证据验证 ｜ 🧪 已编写待运行 ｜ 💭 仅设计 ｜ ❌ 不可行或失败

## A. 环境与证据

| 项 | 状态 | 证据 |
|---|---|---|
| 设备/系统/内核版本实测 | ✅ | `evidence/noroot_20261027_221752/01_device.txt` |
| CPU 拓扑与 cpufreq 策略实测 | ✅ | `02_cpu_topology.txt` |
| 内存 / ZRAM / LMKD 实测 | ✅ | `03_memory.txt` |
| 温控区实测 | ✅ | `04_thermal.txt` |
| 存储与挂载实测 | ✅ | `05_storage.txt` |
| 安全状态实测 | ✅ | `06_security.txt` |
| root 可用性事实核查 | ✅ | `07_root_facts.txt` |
| A 槽备份基线核验 5/5 PASS | ✅ | `08_bootguard_baseline.txt` |
| 内核 config / KMI / Module.symvers | ❌ | 需 root，`/proc/config.gz` 拒读 |

## B. 构建

| 项 | 状态 | 说明 |
|---|---|---|
| 本机编译 GKI 内核 | ❌ | aarch64 主机，AOSP 预编译 clang/Kleaf 仅 x86_64；不可绕过 |
| 锁定版本的远程构建配置 | 🧪 | `build/gki_actions.yml`，需你在自己 fork 里点 Run workflow |
| 本机产出 Image | ❌ | 不存在 |

## C. Root 与内核扩展

| 项 | 状态 | 说明 |
|---|---|---|
| SukiSU Ultra LKM 现状确认 | ❌ 无法确认 | `/sys/module` 列举被 SELinux 拒绝 |
| 现有 init_boot 与 patched 产物比对 | ✅ | A 槽 `init_boot_a.img`=`e70351d2…`，与 `kernelsu_patched_20261027_025206/030639/103008` 字节完全相同 |
| 另一批 patched 产物 | ✅ | `init_boot.img`=`0fc9dc7c…` = `kernelsu_patched_20261026_210859/212337` |
| stock 原厂 init_boot | ✅ | `init_boot-stock.img`=`1d384561…`（与上面两者都不同） |
| SukiSU 补丁脚本/PR | 💭 | 依赖远程构建验证 |
| SUSFS 补丁 | 💭 | 同上 |
| KPM（默认不自动加载） | 💭 | 同上 |
| Magic Mount / Zygisk Next | ✅ | 属 userspace 模块，不需要内核补丁 |

## D. 内存管理

| 项 | 状态 | 实测/说明 |
|---|---|---|
| MGLRU | ❌ 当前未启用 | `/sys/kernel/mm/lru_gen/enabled` 不存在 |
| PSI | ❌ 无法确认 | `/proc/pressure/*` 对 untrusted_app 拒读 |
| ZRAM | ✅ 运行中 | `SwapTotal=16777212 kB`，`SwapFree=10601808 kB`（已用约 6.1 GB） |
| zram 压缩算法 | ❌ 无法读取 | `/sys/block/zram0/comp_algorithm` 不可读 |
| LMKD | ✅ 运行中 | `init.svc.lmkd=running`，`persist.sys.stability.swapEnable=false` |
| LZ4/LZ4KD/ZSTD 选择 | 💭 | 无算法实测数据前不做决定 |
| ZRAM writeback | ❌ 不纳入首版 | 需 backing device，风险与寿命代价不明 |

## E. CPU 调度（VAS）

| 项 | 状态 | 说明 |
|---|---|---|
| 原厂调度路径分析 | ✅ | 实测 governor=`walt`，可见 `walt conservative powersave performance schedutil` |
| A710/A715 差异化前提 | ⚠️ 受限 | 实测 cpu3–6 **共用 policy3**，单一频率域，无法分别定频 |
| 三档 profile 调参层 | 🧪 | `scripts/vas_apply.sh` + `configs/*/vas_profile.conf`，需 root 验证 |
| 自研内核调度器代码 | 💭 | 设计见 `patches/scheduler-vas/DESIGN.md`，不进正式分支 |
| EEVDF 分支 | ❌ | 不混入，KMI 风险 |

## F. 其他内核技术

| 项 | 状态 |
|---|---|
| BBR / F2FS / fs-verity / eBPF / KCFI | 💭 5.15 GKI 已含，路线是验证与调参而非重打补丁 |
| I/O 调度 | 💭 待 root 后读 `/sys/block/*/queue/scheduler` |
| GPU 降压/超频、sched_ext | ❌ 明确不做 |

## G. BootGuard

| 项 | 状态 | 说明 |
|---|---|---|
| A 槽 5 分区基线核验 | ✅ | 全 PASS |
| 只读预检脚本 | 🧪 | `bootguard/preflight/preflight_check.sh` |
| 写操作防护设计 | 💭 | 见 `docs/02_BootGuard操作指南.md` |
| 无人值守双次失败自动回退 | ❌ | 依赖 bootloader 能力，未验证 ⇒ 不实现、不声称 |
| TWRP 应急恢复 | ✅ 已有（历史） | 本次未触碰 |

## 汇总（禁止互相替代）

- 代码完成率：本仓库文件已落地，但**内核源码补丁 0 行**（无构建环境）
- 构建成功情况：**0 次真实内核构建**
- 自动化测试通过率：BootGuard 基线核验 5/5 PASS；其余用例未具备运行条件
- 模拟恢复测试：未开始（缺 root 与可写通道）
- 真机启动验证：**0 次**（且不由 AI 执行）
- 实际安全部署状态：**未部署任何新内核**
