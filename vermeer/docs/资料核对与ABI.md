# 资料核对与 ABI/KMI 门禁

## 三组资料必须分开

1. 初始任务书：`5.15.178-android13-8-00021-g6f2f96be86b9-ab13729987`，SukiSU LKM 正常运行。
2. 本机历史镜像：`Desktop/K70/diagnostics-20261001/boot_b-before.img`，重新计算 SHA-256 为 `5b030bc2a740166fa9c34daa851f5174199067332675abe200245fe11473a95e`，等于用户历史 boot_a 基线。文件名中的 b 不代表当前手机槽位。其 Image 与配置已离线解析，保存于 `evidence/historical-boot-inspection.json`、`configs/baseline/historical-5.15.178.config`。
3. 后续上传说明声称当前正常运行 `5.15.178-android13-8-g362d545d31a5`。上传配置 SHA-256 为 `71ebdb121e6cdcb647b2a2be0235f1bf6f6dbce5e10bf824da1ad4350e4b4289`，与历史配置相差 96 项；与本机 `android13-5.15.178-2025-03-AnyKernel3.zip` 内 Image 提取配置语义完全一致，包含 KSU=y、SUSFS、BBR3 等。完整重查结果见 `evidence/local-packages-rechecked.json`。

现在把第 3 组作为用户新报告的目标状态；第 2 组仅用于原始参考编译。尚未获得当前 boot 分区读回和当前 vendor/system dlkm，不能声称已核实运行镜像。SUSFS 本身支持版本/配置展示修改，因此匹配字符串仍不能替代镜像哈希。

## 对上传操作建议的更正

- Google ACK `build.config.common` 设 `KMI_GENERATION=8`。`android13-8` 不是“小米新增 8 个 commit”。
- `362d545d31a5659546d5546c7ae206f745e98c3e` 是公开 ACK 提交，提交时间 2025-12-17，主题是 vivo KMI 符号列表更新；该提交 Makefile 的 SUBLEVEL 确为 178。并非仅从小米私有树才能取得。
- `CONFIG_KSU=y` 是 built-in 配置；`CONFIG_KSU=m` 才是模块。`__initstub__kmod_*` 可来自 built-in 的 LTO initcall 宏，不能凭这个名字判定未加载 LKM。内建代码不需要出现在 lsmod；符号缺失还可能受隐藏、裁剪、权限等影响。是否实际提供 Root 服务需独立运行证据。
- `CONFIG_MODULE_SIG_PROTECT` 在此 ACK 的 `init/Kconfig` 中就存在，是 Android GKI 受保护符号/导出机制，不是已证实的小米私有功能，也不等于所有未签名模块一律拒绝。
- `CONFIG_GKI_HIDDEN_*` 同样不能单凭名字判定为小米变体。
- GitHub Actions whitelist 路径说明构建目录布局，不能唯一确定仓库所有者、源码分支、workflow commit 或补丁哈希。已找到 WildKernels 及其他同名 fork；没有唯一的原包 release/run 证据前不冒认来源。
- `modules_prepare` 不生成完整 Module.symvers；必须完成内核构建。
- 固定历史 commit 不等于拉取最新 ACK HEAD；本项目没有用最新 5.15.202 冒充 5.15.178。
- 不修改版本字符串来伪装原始签名内核，不通过去掉 dirty 标记证明 ABI，也不执行附件中的关闭 AVB/刷写命令。

## 离线工具的能力边界

`scripts/kernel_audit.py` 可解析 boot/init_boot v3/v4、vendor_boot v3/v4（包括 ramdisk table 边界）、DTBO 表、vbmeta 基本结构、AVB footer 边界、ARM64 Image、IKCONFIG。它不验证 AVB 加密签名、链式描述符、rollback index、SPL 与设备策略；结构成功不等于镜像可启动。

模块检查支持小端 AArch64 ELF64 ET_REL，读取 `.modinfo`、未解析全局符号、`__versions` 的 64 字节 CRC 记录；可与 Module.symvers 对比。gzip/xz 模块可读取，zstd 模块应先在隔离目录解压。仅 CRC 和 vermagic 通过仍不意味着完整 ABI 通过。真实模块 inventory 还必须覆盖压缩模块、模块签名、模块间依赖和所有 boot/vendor_boot/vendor/system dlkm 加载路径。

完整门禁需要当前系统模块集合 + 候选 vmlinux/GKI 模块 + 精确导出符号列表 + ABI 类型图比较。官方 Android13 ABI 以 libabigail 为基础；本机工具版本已记录，但尚未取得厂商参考 vmlinux/ABI，不能把与公开 ACK XML 的比较称为小米当前 ABI 认证。

## 暂停可刷写发布的条件

当前运行来源/Root 状态冲突尚未独立解决；完整五分区最新备份未到齐；当前 dlkm 缺失；SUSFS 与正式 SukiSU 的确切兼容组合尚未建立；BootControl 重试/成功标记时机未实测。任一未解决都阻止 boot.img/刷机安装包发布。

来源：[Android ABI 文档](https://source.android.com/docs/core/architecture/kernel/abi-monitor)、[历史 ACK](https://android.googlesource.com/kernel/common/+/6f2f96be86b93de6ed58a2c46b456fb49734c382)、[新报告目标 ACK](https://android.googlesource.com/kernel/common/+/362d545d31a5659546d5546c7ae206f745e98c3e)。原始响应及哈希保存在 evidence。
