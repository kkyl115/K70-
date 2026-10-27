# 上游源码与工具链锁定清单
# 状态: 💭 待远程构建验证（本机 aarch64 无法编译 GKI）

## 1. 内核源码（推荐路线：ACK，不是小米 vendor 树）

| 项 | 值 | 说明 |
|---|---|---|
| 仓库 | `https://android.googlesource.com/kernel/common` | Android Common Kernel |
| 分支 | `android13-5.15`（对应 GKI 5.15.178） | 必须与设备 KMI 系列一致 |
| sub_level | **178**（严禁随意跳） | 与当前 `uname -r` 对齐 |
| 安全补丁级别 | **按实测校准**：本机 `ro.build.version.security_patch` 需复核 | 早期误用 `2025-03`，与系统 2026-03 不匹配 |
| 镜像 | `https://android.googlesource.com/kernel/common` + `mirrors.edge.kernel.org` | |

### 为什么不选小米 `bsp-vermeer-t-oss`

- 该分支存在，但 `T` = Android 13 代；本机是 HyperOS 3.0.302（Android 16）。
- 设备跑的是 **GKI `android13-5.15`**，替换内核必须来自 ACK，vendor 树的符号表/vermagic 与 `vendor_dlkm` 不匹配 → 卡 Logo。
- 结论：vendor 树只用于**读取设备树与厂商改动参考**，不作为构建源。

## 2. Root / 内核扩展

| 项目 | 版本/commit | 状态 |
|---|---|---|
| SukiSU Ultra | 目标 `v4.2.1-r2`（与现有管理器一致，commit 待联网核对 `d6b3670…`） | 💭 |
| SUSFS | `ShirkNeko/susfs4ksu`，`v2.3.0`（来自 build.py 实测输出） | 💭 |
| KPM | SukiSU 内置开关 `use_kpm` | 💭 首版默认**不自动加载**任何 KPM 补丁 |
| Magic Mount / Zygisk Next | userspace 模块，不涉及内核补丁 | ✅ |

**硬规则**：现有是 LKM 形态。若最终产物为 built-in，则刷写前必须先用 stock `init_boot` 撤掉 LKM，禁止两套叠加。

## 3. 工具链

| 项 | 值 |
|---|---|
| 编译器 | AOSP 预编译 clang（与 ACK 分支 `build.config` 声明一致），**仅 x86_64 版** |
| 构建系统 | Kleaf / Bazel（ACK 5.15 官方方式）；不走裸 make |
| 主机要求 | x86_64 Linux，≥100 GB 空闲磁盘，≥16 GB RAM |

本机为 aarch64 Android + Termux，**不满足主机要求**，故所有构建必须走远程 x86_64（GitHub Actions 或你自己的电脑）。

## 4. 构建参数（钉死，不允许漂移）

```yaml
android: android13
kernel: 5.15
sub_level: 178
os_patch: <实测值，需与 ro.build.version.security_patch 一致>
ksu_commit: <v4.2.1-r2 对应 commit，联网后写入>
susfs: v2.3.0
use_kpm: true
zram: 保持原厂（首版不改算法）
workspace: $HOME/gki-build    # 不要用 /tmp（本机 /tmp 不可写）
```

## 5. 待补的实测值

- [ ] `ro.build.version.security_patch`
- [ ] `ro.boot.slot_suffix` 与 vbmeta 状态（已有部分，见 evidence）
- [ ] `/proc/config.gz`（需 root，判断 MGLRU/PSI/ZRAM 算法/KCFI）
- [ ] `Module.symvers` 与 `abi_gki_aarch64.stg` 差异（编译后才有）
