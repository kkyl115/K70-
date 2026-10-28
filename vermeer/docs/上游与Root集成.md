# 上游锁定与 Root 集成边界

所有已获取引用见 `sources/upstream-lock.json`，原始 API 响应、获取时间、URL、SHA-256 在 `evidence/upstream-research/`。不执行网络脚本，不在 commit 不存在时退回 HEAD。

| 来源 | 固定提交 | 用途 |
|---|---|---|
| Google ACK | 6f2f96be86b93de6ed58a2c46b456fb49734c382 | 历史原始参考编译 |
| Google ACK | 362d545d31a5659546d5546c7ae206f745e98c3e | 新报告目标 ACK；缺原 CI 附加补丁 |
| MiCode bsp-vermeer-t-oss | 53ef33eacdc4f7ac737451e4cfc91963d59e3956 | Android U BSP/WALT 研究 |
| SukiSU v4.2.1-r2 | d6b36700f3bd0a4c1585549b470dd30bb8774534 | 正式版本源码，离线 LKM 编译实验 |
| SUSFS gki-android13-5.15 | 0b5f96716cb2fc7b035dce2f06cb8a51e1b9b108 | 官方匹配系列补丁；尚未选为兼容发布版本 |
| SukiSU KernelPatch | bc2bf170c3251a849ecf52e98ff66b6df7160415 | KPM 源码调查；未应用 |

日期保存在 API metadata，不用抓取日冒充发布日期。SukiSU tag 的 release published_at 与 commit date 分别保存；SUSFS 分支 HEAD 只作为固定调查快照，并非已认证稳定发布。MiCode 分支名虽有 t，提交说明为 Android U，不能从后缀推断当前兼容性。

## 实际源码与集成脚本

SukiSU、KPM 完整固定源码 tar.gz 位于 `evidence/upstream-research`；SUSFS 原始补丁和支持 C/header 文件位于 `patches/susfs`。`prepare-root.py` 验证下载哈希/固定提交、拒绝覆盖已有目标，解压到隔离目录。它生成并应用 `patches/sukisu/0001-pin-offline-version.patch`，删除上游 Kbuild 在编译时读取 GitHub latest/commit count 和自动 fetch 的行为，固定 41068 与源码标识；保留 manager 签名检查默认值。

`build-root-lkm.sh` 只在参考内核已生成 Module.symvers 后执行 Kbuild 外部模块编译，明确 CONFIG_KSU=m、CONFIG_KPM=n。它是独立研究产物，绝不可直接加载到当前手机。参考内核版本含 lab 标识，故也不声称 vermagic 与设备一致。

主线与 builtin 分支不能互换。本次正式 tag 的 Kconfig 并无完整 SUSFS 开关；其扩展管理代码存在也不等于内核已实现全部 SUSFS patch。SUSFS README 指出主要针对原版 KernelSU，提供的 `10_enable_susfs_for_ksu.patch` 不能盲目套到重构后的 SukiSU。两套 ACK 的 `git apply --check` 均在 `fs/namespace.c` 与 `fs/proc/task_mmu.c` 拒绝，日志已保存。未经源码级修复、单项编译、ABI 检查，不进入全功能构建。

## KPM

SukiSU 的 KPM 接口文件中仍有供 KernelPatch 接管的 stub；只设 CONFIG_KPM=y 并不证明框架可用。完整 KernelPatch 源码已固定获取，但未对 Image 做任何二进制 patch。当前 CONFIG_KPM=n，不加载任何 KPM 模块。

未来若启用：每个原始 Image 需独立哈希和 patch ledger，已 patch 输入直接拒绝；固定 patcher 源码/编译器及产物哈希；核验每个扩展的来源、内容哈希、签名信任链、架构与内核版本；默认空允许列表和零自动加载。当前未验证 KPM 自身是否满足所需签名策略，因此不以普通 SHA256 冒充签名校验。

## Root 生命周期/用户空间

现有 Root 状态需由当前 boot/init_boot 和服务状态共同核实。CONFIG_KSU=y 的自定义内核上禁止叠加 LKM。切换内建方案需要独立完成旧 LKM 安装链清除、重启验证和可恢复备份，不能通过更新 APK 后“直接安装”升级内建内核。

Magic Mount、Zygisk Next、模块安装卸载属于内核、ksud、管理器与用户空间模块的组合测试。此仓库不会以一个内核 CONFIG 选项冒充兼容性验证。必须固定具体用户空间版本，测试安装/禁用/卸载/重启残留、SELinux enforcing、应用隔离、mount namespace、boot-completed 阶段及恢复入口；当前这些实机项目未执行。

SukiSU 仓库根许可证 GPL-3.0，kernel/LICENSE 为 GPL-2.0；SUSFS 根许可证 GPL-3.0，具体文件保留原 SPDX/版权；ACK/MiCode 保留 COPYING 与逐文件许可。补丁与派生发行前仍需逐文件核对，未把所有第三方源代码重新授权为项目自有许可。

上下文修复实验：`scripts/rebase-susfs-context.py` 生成替代的 `51_susfs_ack_context_rebased.patch`，仅移除目标源文件中不存在的两个 trace include 上下文（50 与 51 不能同时应用）。过程中修复了 Windows 写补丁 CRLF 的问题，保留失败日志。修复后两套 ACK 均继续在 `show_smap()` 拒绝：实际源码使用 `get_pad_vma/get_data_vma`，原补丁假设 `vma=v`。需要审查 padding VMA 与 SUSFS 的语义，当前 51 仍不是可用的集成补丁，不自动应用。

追查 CI：已获取 WildKernels/GKI_KernelSU_SUSFS 固定 workflow 快照 `222173a6397e27bcc6461d4600c3ecb5d8ac61da`，仓库顶层无内核 Makefile，是构建编排来源线索；不能按附件命令把它当作完整内核树并 checkout ACK commit。仍缺实际安装包对应的 workflow/run 与所有依赖 pins。

官方参考：[SukiSU](https://github.com/SukiSU-Ultra/SukiSU-Ultra)、[SUSFS](https://gitlab.com/simonpunk/susfs4ksu)、[KPM](https://github.com/SukiSU-Ultra/SukiSU_KernelPatch_patch)。下载源码不等于已验证运行。
# 补充：2026-10-28 独立对象编译

锁定正式版的 kernelsu.o 已在历史 ACK 5.15 的独立输出目录编译成功，KPM 未激活、没有合并 SUSFS。首次错误是缺少 SELinux 生成的 flask.h；modules_prepare 不覆盖这一依赖，通过构建 security/selinux 子目录解决，未伪造头文件。见 `evidence/root-object-attempt1-missing-flask.log`、`root-object-selinux-prerequisite.log`、`root-object-build.log`、`root-object-result.json`。这尚不是完整 .ko 链接/CRC 验收或实机运行通过。

