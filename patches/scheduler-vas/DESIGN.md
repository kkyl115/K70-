# Vermeer Adaptive Scheduler (VAS) 设计说明

状态：💭 **仅设计 + 只读分析**。本文件不含已编译的内核代码，也不含任何性能数字。
原因：本机 aarch64 无法编译 GKI；且直接修改 `kernel/sched/` 会破坏 GKI KMI 白名单。

---

## 1. 硬件事实（全部来自本机实测，非推测）

来源：`evidence/noroot_20261027_221752/02_cpu_topology.txt`

| 簇 | CPU | capacity | policy | 频率范围 | 推断核心 |
|---|---|---|---|---|---|
| 小 | cpu0–2 | 280 | policy0 | 307200–2016000 kHz（16 档） | Cortex-A510 ×3 |
| 中 | cpu3–6 | 855 | **policy3（共用）** | 499200–2803200 kHz（19 档） | A715 ×2 + A710 ×2 |
| 大 | cpu7 | 1024 | policy7 | 595200–3187200 kHz（20 档） | Cortex-X3 |

- `scaling_governor = walt`，可选 `walt conservative powersave performance schedutil`
- `/sys/kernel/walt` 不存在（WALT 的 sysfs 接口在本 OEM 内核未暴露或 SELinux 隐藏）
- `uclamp` 接口在 app 权限下未读到，需 root 复核

### 三条设计约束（这些结论直接推翻了一些常见做法）

1. **A715 与 A710 无法分别定频**：两者同属 policy3，单频率表。任何"给 A715 更高频"的方案在 cpufreq 层不可能实现。要做差异化，只能通过 **uclamp_min/uclamp_max 的任务分组**或**唤醒亲和性**间接影响，且必须先确认 uclamp 接口可用。
2. **不要替换 governor**：原厂用 WALT（高通惯用），换 schedutil 会丢掉窗口辅助（window-assisted）负载跟踪，交互延迟通常变差。VAS 只做**参数与策略编排**，不动 governor 主体。
3. **容量差 3 倍（280 / 855 / 1024）**：小核容量太低，把重负载压到小核会显著拉长完成时间；反过来把轻负载留在中核会浪费功耗。这是 VAS 的核心矛盾。

---

## 2. 分层设计

```
┌─────────────────────────────────────────────┐
│ L3  策略编排层（本工程已实现，需 root 生效）  │
│     balanced / performance / efficiency      │
│     工具: scripts/vas_apply.sh + configs/*   │
├─────────────────────────────────────────────┤
│ L2  运行时旋钮（sysfs / procfs / prop，只调参）│
│     sched_* / uclamp / walt boost / thermal  │
├─────────────────────────────────────────────┤
│ L1  内核调度主体（WALT + EAS + cpuidle）      │
│     ❌ 本工程不修改，保持原厂路径             │
└─────────────────────────────────────────────┘
```

**L1 不动是刻意的**：GKI 的 KMI 白名单只覆盖导出符号与结构体布局，改调度器内部逻辑一旦触碰导出结构体，就会让 `vendor_dlkm` 里的模块加载失败 —— 这正是卡 Logo 的一大来源。

---

## 3. 三档策略与参数表

单位、范围、默认值、调整条件、回滚方式全部列出。**当前所有值均为"待实测标定"状态**，标记为 `TBD` 的必须有 A/B 数据才能定稿。

### 3.1 Balanced（日常）

| 参数 | 路径/键 | 单位 | 合法范围 | 默认（本档） | 调整条件 | 回滚 |
|---|---|---|---|---|---|---|
| schedutil/walt 升频速率 | `rate_limit_us` | µs | 0–100000 | TBD（基线值先采集） | 交互掉帧但功耗无压力 → 降 | 记录原值回写 |
| 小核最小频 | policy0 `scaling_min_freq` | kHz | 307200–1017600 | 307200 | 后台任务堆积 → 上调 | 回写 307200 |
| 中核最小频 | policy3 `scaling_min_freq` | kHz | 499200–1017600 | 499200 | 同上 | 回写 499200 |
| 大核最小频 | policy7 `scaling_min_freq` | kHz | 595200 | 595200 | **不建议动** | 回写 595200 |
| 迁移粒度 | `sched_migration_cost_ns` | ns | 0–10 000 000 | 原厂值 | 抖动/迁移过多 → 上调 | 回写原值 |
| 唤醒粒度 | `sched_wakeup_granularity_ns` | ns | 0–20 000 000 | 原厂值 | 响应差 → 下调 | 回写原值 |
| 组调度 | `sched_autogroup_enabled` | 0/1 | 0–1 | 1 | 不调 | — |

### 3.2 Performance（帧稳定优先，不绕温控）

| 参数 | 单位 | 说明 |
|---|---|---|
| 大核最小频 | kHz | 提升到 864000–1209600（**不锁最高频**） |
| 中核最小频 | kHz | 提升到 1017600 左右 |
| walt boost 相关（若可写） | — | 优先提升"渲染线程所在任务的 util 门槛"，而非全局 boost |
| 温控 | — | **不动 thermal，不绕过**；只允许提前让出频率，不提高上限 |

关键纪律：Performance 档**不写 `scaling_max_freq`**，因为一旦写死上限就等于关闭 DVFS 与温控协同，属于任务书明令禁止的"把 governor 参数调到最大"。

### 3.3 Efficiency（续航优先）

| 参数 | 单位 | 说明 |
|---|---|---|
| 小核最小频 | kHz | 307200（最低） |
| 中核最小频 | kHz | 499200（最低） |
| 大核 | — | 保持原厂，靠 EAS 自然下沉 |
| `sched_migration_cost_ns` | ns | 上调以减少无效迁移 |
| `sched_wakeup_granularity_ns` | ns | 上调以减少过度抢占 |

---

## 4. 若要真的写内核代码（未做，仅路线）

| 步骤 | 内容 | 门禁 |
|---|---|---|
| 1 | 在 ACK `android13-5.15` 上 `git log kernel/sched/` 摸清 OEM 已有什么 | 只读 |
| 2 | 纯计算型原型（用户态回放：用 `perf sched` 数据驱动策略函数） | 用户态可编译 |
| 3 | KMI 影响评估：`build/abi/` 比对前后 `Module.symvers` 与 `abi_gki_aarch64.stg` | 必须 0 差异才能继续 |
| 4 | 最小侵入实现：只加 **新的 sysfs 旋钮**，不改导出符号、不改结构体布局 | 编译通过 |
| 5 | A/B 对照：同机型、同版本、同电量、同负载脚本，≥5 轮取中位数 | 有散度才可信 |

**绝不做的**：把 `sched_ext` 移植进来、混 EEVDF、把 PELT 换成自定义跟踪器。

---

## 5. 指标定义（避免"我觉得更快了"）

| 维度 | 采集手段 | 指标 |
|---|---|---|
| 前台响应 | `dumpsys gfxinfo` / `atrace` 帧时长 | p95、p99 帧时（ms） |
| 游戏帧稳定 | 帧时间直方图 | 1% low FPS |
| 迁移抖动 | `/proc/schedstat` 前后差值 | 单位时间迁移次数 |
| 每瓦性能 | 功耗轨（需外设）或 `dumpsys batterystats` 电量速率 | 同任务完成时间的功耗 |
| 温控介入 | `04_thermal.txt` 里各 zone 温度与 cooling cur_state | 出现 >X℃ 的时间占比 |

以上**全部未采集**，因为需要 root + 可重复负载脚本，且 A/B 对照要求系统状态受控。当前不提供任何"提升百分比"。
