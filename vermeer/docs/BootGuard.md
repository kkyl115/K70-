# BootGuard 离线工程与手机操作边界

本版本是安全检查与恢复事务的离线实现。**真实设备写入后端禁用；没有实现或验证手机无人值守自动回退。** 原有用户已验证的救援环境、A 槽与备份没有被本项目修改。TWRP 包是 AUDIT NOOP，不能代替用户已有恢复包。

## 已实现

`bootguard.py verify-backups` 校验五个固定命名文件、字节数和 SHA-256；拒绝缺项、目录穿越、符号链接、Windows reparse point、非普通文件和多硬链接。历史 SHA 只作为对照，不自动授权当前备份。

`preflight` 核对 vermeer、系统构建、Android16、当前 A/目标 B、Virtual A/B、snapshot merge、OTA、SELinux、AVB、最新分区读回与备份是否一致、目标启动链/救援环境、ABI/CRC、Root 模式转换和 BootControl 能力。900 秒以上的采集记录失效，时钟在未来也拒绝。该 900 秒仅是离线过期阈值，不提供防 TOCTOU 的真实设备写入锁。

输入中的“已验证”布尔值是外部证据断言，工具不能自行证明其真实性；即使所有输入通过，输出仍是 `deployable:false`。不会把模拟通过升级为设备批准。

`simulate` 只能在内部新建的临时普通文件目录运行，**不接受目标路径**。模拟 B 的备份、prepared、半写入、written、读回 verified、committed；在各阶段注入中断后重读磁盘 journal，未提交则恢复原 B。A 始终保持不变。坏备份在首次目标写入前拒绝。提交后保留候选。文件 flush/fsync 已执行；Windows/Linux/真实 NAND 的断电语义不同，未模拟所有存储控制器/目录日志撕裂，不声称硬件断电恢复保证。

`BootControlModel` 只在提供已验证 native retry count 的条件下模拟。原生 count=3 不允许冒充“两次失败回退”。若已经过早标记 successful，bootloader 可能不再回退；这必须调查 Android 启动服务/Boot HAL 与 bootloader 实现，内核无法凭空补出这个能力。

## 本地命令

```
python bootguard/bootguard.py simulate --fail-at partial_write
python bootguard/bootguard.py simulate --corrupt-backup
python bootguard/bootguard.py verify-backups <副本目录> <manifest.json>
python bootguard/bootguard.py preflight <observation.json> <backup-result.json>
```

manifest 顶层严格包含 boot_a/init_boot_a/vendor_boot_a/dtbo_a/vbmeta_a；每项为 `{"file":"boot_a.img","bytes":实际大小,"sha256":"实际哈希"}` 等。不能把手机路径 `/sdcard/Download/BootGuard/A_backup_20261027_124239` 当作电脑本地已有文件。不要修改原始备份，可在副本上验证。

## 无电脑条件下的使用范围

`preflight/collect-readonly.sh` 是供所有者自行选择运行的只读采集脚本。本会话没有运行它，没有 adb/fastboot 手机调用。它不自动提权、不改变槽位、不 mark-success、不挂载分区、不写入分区。受限读取失败输出会缺项，不能当作正常值。

生成的 `BootGuard-AUDIT-NOOP.zip` 可通过 TWRP 的触屏 Install 流程调用仅审计脚本，验证型号/当前槽位并输出“NOOP”；尚未在 TWRP 真机执行。**它不能恢复卡 Logo。** 当前应继续保留用户已有且实机验证过的应急恢复包。未获得当前五镜像与救援链证据前，本项目不制作写入型恢复 ZIP。

真正部署还需检查 B 的 boot/init_boot/vendor_boot/dtbo/vbmeta 与当前共享 system/vendor 的组合、AVB descriptor/rollback/SPL、snapshot merge、实际救援入口和供电条件。B Successful 不等于该组合可启动。Fastboot 不能默认读取 sdcard。不得以破坏 A 或系统数据的方式验证回退。

官方参考：[A/B bootloader](https://source.android.com/docs/core/ota/ab/ab_implement)、[Virtual A/B](https://source.android.com/docs/core/ota/virtual_ab)。原生 API 并不提供通用的任意 retry count 设置保证。
