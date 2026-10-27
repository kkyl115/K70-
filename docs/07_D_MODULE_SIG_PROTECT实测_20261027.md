# D｜MODULE_SIG_PROTECT 实测：未签名/自签模块是否被拒载

日期：2026-10-27
结论：**不拒载。** 结论由「静态证据 + 真实 insmod 实测」双重确认。

## 一、静态证据

### 1. vendor 模块本身就没有签名段
- `adsp_loader_dlkm.ko`：readelf -S 共 30 个段，**无 `.module_sig` 段**（最后三段是 .symtab/.shstrtab/.strtab）。
- `coresight-dummy.ko`：`readelf -S | grep -ic module_sig` 输出 `0`，**无签名段**。
- 结论：小米 vendor_dlkm 的 .ko 靠分区级 AVB 保护，不靠逐模块签名。

### 2. /proc/modules 里所有模块都带 E / OE
- `(E)` = TAINT_UNSIGNED_MODULE（未签名 taint）
- `(OE)` = out-of-tree + unsigned
- 实测样例：`kiwi_v2 ... (OE)`、`msm_drm ... (OE)`、`coresight_tmc ... (E)`、`coresight ... (E)`
- 结论：内核一直在放行未签名模块，且如实打上 taint 标记。

### 3. 关键配置（源自本机 kernel_config 提取）
```
CONFIG_MODULE_SIG=y
# CONFIG_MODULE_SIG_FORCE is not set   ← 不强制验签
CONFIG_MODULE_SIG_PROTECT=y            ← Android 保护，但 FORCE 未开时只打 taint 不拒载
CONFIG_MODULE_SIG_ALL=y
CONFIG_MODULE_SIG_HASH="sha1"
```

## 二、真实 insmod 实测（可复现）

步骤：
1. `cp /vendor_dlkm/lib/modules/coresight-dummy.ko /data/local/tmp/d_test.ko`（复制到**非 vendor 路径**，排除路径白名单因素）
2. `insmod ./d_test.ko` → **exit 0，成功**
3. `/proc/modules` 出现独立行：
   `coresight_dummy 16384 0 - Live 0x0000000000000000 (E)`
4. `rmmod coresight_dummy` → **exit 0，成功**
5. 删除副本。

结果：从 /data/local/tmp 加载**无签名**模块，内核直接放行，仅打 `(E)` 标记，**无签名拒绝、无路径保护拦截**。

## 三、结论与意义

| 疑问 | 结论 |
|------|------|
| MODULE_SIG_PROTECT 会拒载自签/未签名模块吗？ | **不会**（实测） |
| 签名验证能不能"关掉"？ | 不用关，本来就非强制（FORCE not set） |
| 运行时有没有开关？ | 无，MODULE_SIG_* 全是编译期项 |
| 对重编内核的意义 | 自编模块只要 vermagic + Module.symvers CRC 对上，即可直接 insmod，**无需签名** |

### 重编的真正硬门槛（重新确认）
不是签名，而是：
1. **vermagic 对齐**：5.15.78（vendor KMI）+ aarch64 + modversions
2. **Module.symvers CRC 对齐**：自编模块导出的符号 CRC 必须与内核已导出符号一致（尤其依赖 `coresight` 这类框架符号时）
3. **工具链**：Android 内核需 x86_64 交叉编译链（Termux aarch64 编不了）

### 附注
- dmesg 中未捕获到 insmod/coresight_dummy 的加载日志（内核 printk 对模块加载静默或 klog 读取受限），不影响结论，以 /proc/modules 铁证为准。
- 本次测试模块 coresight-dummy 为无害调试驱动，加载后已立即卸载，无残留。
