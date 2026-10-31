# Vermeer Ultimate Kernel + BootGuard

Redmi K70 / vermeer 的离线工程工作区。**当前不是稳定内核或可刷写安装包。** 已在机主授权后做只读采集；没有覆盖 A 槽、修改槽位、调整手机参数或关闭 AVB/SELinux。

- [下一阶段技术与调参门禁](docs/下一阶段技术与调参门禁.md)：首轮实机只读数据、WALT 三策略域、MGLRU 关闭状态和可实现方向。
- [2026-10-31 当前内核核验](docs/当前内核核验-20261031.md)：新 ZIP 的 BBG/LZ4KD/KPM 实证、NoActive 配套关系和版本差异。
- [验收报告](docs/验收报告.md)：分别说明代码、编译、自动化测试、模拟恢复与实机状态。
- [技术路线与新想法](docs/技术路线与新想法.md)：BBG、BBRv3、NTSync、WireGuard、DroidSpaces、ZRAM、DAMON 等用途和真实限制。
- [构建与操作指南](docs/构建与操作指南.md)：锁定源码/Clang、本地测试、待补资料。
- [Root 集成](docs/上游与Root集成.md)、[ABI 核对](docs/资料核对与ABI.md)、[VAS](docs/VAS.md)、[BootGuard](docs/BootGuard.md)。

历史 ACK 基线是 `6f2f96be86b93de6ed58a2c46b456fb49734c382`；后来上传资料报告的当前内核基于 `362d545d31a5659546d5546c7ae206f745e98c3e` 并带第三方补丁，二者严格分开。2026-10-31 新 ZIP 内同为 g362d 字符串，但功能配置不同；截图显示 g8f7，与 ZIP 的字节级关联尚未完成。当前完整 patch 来源和对应 vendor/system_dlkm 仍未齐备。

## 可直接运行的离线部分

```sh
bash scripts/test.sh
python3 scripts/audit-features.py configs/baseline/user-supplied-5.15.178.config
```

Windows 的 `build.ps1` 调用 WSL 构建历史基线。`scripts/bootstrap.sh` 获取锁定源码/工具链；完整构建保留 full LTO/CFI。宿主机依赖和内存条件见日志，不保证在任意 16GB 主机均能完成链接。

VAS 是真实 C 算法原型，尚未接入厂商调度路径；三套策略默认只观察且参数未经实机校准。BootGuard 提供离线校验、失败注入/回退模型及 TWRP AUDIT-NOOP；NOOP 包不能救砖，真实分区写入后端未启用。

`ci/vermeer-offline.yml` 是交付仓库独立工作流模板：普通推送只做离线测试，完整编译须手动选择。没有自动发布、Telegram 通知、手机操作或无人值守安全回退的承诺。
