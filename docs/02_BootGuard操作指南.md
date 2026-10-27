# BootGuard 操作指南（当前版本：只读）

## 0. 当前能力边界（务必先读）

| 能力 | 状态 |
|---|---|
| A 槽 5 分区备份哈希核验 | ✅ 可运行，已 PASS |
| 设备身份 / 槽位 / AVB 状态检查 | ✅ 只读 |
| boot 镜像 header magic 检查 | ✅ 只读 |
| 备份目录自校验 | ✅ 只读 |
| 写入任何分区 | ❌ **本版本没有写路径** |
| 切槽 | ❌ 无 |
| 无人值守双次失败自动回退 | ❌ **未实现**（需 bootloader 能力验证，不能凭空声称） |
| TWRP 应急恢复 | ✅ 历史已有，本次未改动 |

## 1. 跑预检

```bash
bash /storage/emulated/0/Download/vermeer-ultimate-kernel/bootguard/preflight/preflight_check.sh
```

输出末尾会给出：
```
RESULT=PASS  FAIL=0 WARN=n
```
或
```
RESULT=FAIL  FAIL=n WARN=n   → 禁止任何刷写
```

退出码：`0` 通过 / `1` 有 FAIL / `2` 严重（缺备份或型号不符）。

## 2. 已知的四条硬约束（不是建议，是结论）

1. **Virtual A/B ≠ 两套完整系统。** `super` 内动态分区共享物理区域，切到 B 不等于拥有独立的可用系统数据。
2. **Fastboot 模式读不到 `/sdcard`。** 备份在内部存储里，fastboot 下不可见；恢复必须经由 TWRP 或已开机的 Android。
3. **改内核不能给 bootloader 增加能力。** "连续两次失败自动回退到另一槽"需要 bootloader 支持并已启用该逻辑；无法验证就不能承诺。
4. **B 槽标记 Successful 不代表能启动。** 该标记由 Android userspace 写，与镜像可用性无关。

## 3. 若将来要写（本版本未实现，仅记录规则）

任何写操作脚本必须同时满足：

1. `--allow-write` 显式传入 + 交互输入 `I-UNDERSTAND-WRITE-<slot>` 二次确认
2. 写前重新核验：型号、代号、slot_suffix、目标镜像 SHA-256、剩余空间
3. 目标槽位必须是**非当前运行槽**，且当前槽备份哈希仍与基线一致
4. 写前把目标分区前 N MB 原样 dump 到 `bootguard/rollback/`（可逆性证明）
5. 写入后立刻 `sync` 并再次读回哈希比对
6. 中断处理：`trap` 捕获 INT/TERM，未完成则标记 `INCOMPLETE` 并保留 dump
7. 全程日志写入 `evidence/`，含时间戳、每步返回值

**目标槽位写入实现后，仍需你在真机上验证启动，AI 不执行刷写。**

## 4. 回滚基线（当前有效）

目录：`/storage/emulated/0/Download/BootGuard/A_backup_20261027_124239`

| 分区 | SHA-256（实测一致） |
|---|---|
| boot_a.img | `5b030bc2a740166fa9c34daa851f5174199067332675abe200245fe11473a95e` |
| init_boot_a.img | `e70351d22243ce995bec0fc755dc8e2c63cb161f0dcb16bd11366f6937ca9e7a` |
| vendor_boot_a.img | `45320eae7815fa043f0e4034cd4ae33cf423ed8d546a7815ff439c7a7b86a040` |
| dtbo_a.img | `aac33c81251f8789a32eb4330067b86bc5853b58c1101ca9a7699041178232df` |
| vbmeta_a.img | `403175daae8c10b1e2c2ec40f83980480edafd2c9a84a9cc28f9170ce7cbe1a9` |

**不要修改或删除该目录下任何文件。** 预检脚本只读取它。

## 5. init_boot 变体的疑点（需你确认）

实测发现三份互不相同的 init_boot：

| 文件 | SHA-256 |
|---|---|
| A 槽备份 `init_boot_a.img` | `e70351d2…9e7a` |
| `kernelsu_patched_20261027_025206/030639/103008.img` | `e70351d2…9e7a`（与 A 槽**完全相同**） |
| `init_boot.img` / `kernelsu_patched_20261026_210859/212337.img` | `0fc9dc7c…4904` |
| `init_boot-stock.img` | `1d384561…b41a` |

真正的 SukiSU-LKM 打补丁必然改变字节（插入 `kernelsu.ko`、改 ramdisk）。这批 "patched" 文件与源镜像字节一致，说明**它们不是有效补丁产物**，不能当作"补丁成功"的证据。

另外 `SukiSU_install_log_2026-10-27-04-10-40.log` 记录了一次失败：
```
Bootdevice: /dev/block/by-name/boot_b
Patch Error: open /dev/block/by-name/boot_b → Permission denied (os error 13)
```
- 说明在无 root 的进程里打补丁必然失败
- 且目标是 **boot_b**（B 槽），与"A 槽不动、也别乱动 B 槽"的原则冲突，**该路径应禁用**
