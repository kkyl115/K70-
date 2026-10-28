# Vermeer Adaptive Scheduler 研究原型

当前交付是能编译、测试、回放的 C 决策核心与内核编译探针。没有接管手机调度，没有实测性能增益，不是正式调度器。三个 JSON 配置默认 `observe_only=true`。

## 原厂路径调查

已获取 MiCode `53ef33eacdc4f7ac737451e4cfc91963d59e3956` 的 `kernel/sched/walt/walt.c`、`walt.h`、`cpufreq_walt.c`。后者说明基于 schedutil 修改，包含 up/down rate limit、uclamp 汇总等路径。但该公开 BSP 是旧 Android U 基础，不能据此证明当前运行的 WALT 模块版本。ACK 的 fair.c、cpufreq_schedutil.c、PELT、cpuidle 和 thermal pressure 仍保留原样。

目标接入应先确认运行时调度器及模块/hook 所有权。ACK `include/trace/hooks/sched.h` 的 `android_rvh_select_task_rq_fair(p,prev_cpu,sd_flag,wake_flags,new_cpu)` 是调查入口，**不是可以随意叠加注册的安全接口**。厂商 restricted hook 的注册限制、已有 WALT 回调及生命周期必须核查。不得用一个空闲 hook 的假设替代这些检查。

## 核心实现

`patches/scheduler-vas/vas_core.c` 使用定长输入，无堆分配、锁、I/O 和内核全局变量。`vas_cpu` 记录 CPU id、独立核心种类 A510/A710/A715/X3、capacity、thermal_pressure、util、校准能耗成本及 online。CPUFreq policy 数量与 CPU 种类无关，算法不根据 policy 编号识别核心。

`vas_task` 提供任务 util、等待延迟、交互标记、CPU affinity mask、上次迁移时间。`vas_state` 保存 util/wait 的 1/8 新样本 EWMA。`vas_update` 与选核是分离 API，当前调用者必须显式选择 raw 或 EWMA 输入；没有声称已经集成任务级内核状态。

候选 CPU 首先经过 online、affinity、有效容量 `capacity - thermal_pressure` 过滤。成本为：

```
demand = (cpu_util + task_util) * 1024 / effective_capacity
cost = calibrated_energy_cost * energy_weight
     + demand² * latency_weight / 1024
若交互等待超过预算：再加 demand * floor(wait_us / budget_us) * latency_weight
```

这是无量纲启发式成本，不是瓦特或实际完成时间。A710/A715 分别使用自己的实测输入，不假定谁永远更省电。X3 仅凭容量、拥塞与成本竞争；没有强制频率、最高 governor 参数或温控绕过。迁移 hold 和最小成本改善门限减少抖动；原 CPU 不可用/容量不足时不能让 hold 覆盖安全过滤。无可用 CPU 或输入非法返回 -1，调用者必须交还原调度器。公平性仅有凸拥塞惩罚，不等价于 CFS/WALT 的完整公平保证；正式接入仍必须保留原框架公平性和 RT/DL 优先级。

`vas_probe.c` 是共享 C 核心的内核编译探针，只运行一次内部检查，不注册 scheduler hook；不可把探针编译成功称为调度集成完成。

## 参数表

所有默认值来自明确标注的研究假设，尚无实机参数标定，因此只允许观察模式。范围由 C 输入校验执行。

| 参数 | 单位/范围 | Balanced | Performance | Efficiency | 调整依据 |
|---|---|---:|---:|---:|---|
| latency_budget_us | μs，1..1000000 | 4000 | 2000 | 6000 | runnable-to-running p95/p99、帧 deadline |
| migration_hold_us | μs，0..1000000 | 4000 | 2000 | 8000 | 迁移/任务/秒、cache miss、尾延迟 |
| improvement_permille | 千分比，0..1000 | 120 | 80 | 200 | 往返迁移与等待延迟权衡 |
| energy_weight | 无量纲，1..1000 | 100 | 70 | 160 | 同工作量焦耳与温控区间 |
| latency_weight | 无量纲，1..1000 | 100 | 160 | 70 | 帧稳定性、交互尾延迟 |
| observe_only | bool | true | true | true | 无实机/ABI证据不得关闭 |
| EWMA 新样本权重 | 固定 1/8 | 1/8 | 1/8 | 1/8 | 仅研究常数，修改需重新回放 |

回滚：当前没有应用行为，退出研究工具即可；未来接入必须具备默认关闭的静态开关并立即回到原选核结果，不能通过换 profile 代替禁用。禁止在调度热路径读 JSON；JSON 仅是实验配置输入。

## 验证与实机 A/B 方法

测试含 affinity、offline、thermal、时钟倒退、重复 CPU、迟滞、A710/A715 独立输入、EWMA，以及固定种子的 10000 组随机安全约束检查。`evidence/vas-synthetic-replay.json` 是 600 步合成决策回放，只显示选择/变化次数；不模拟真实任务执行，不能推导功耗或速度提升。

实机阶段应先采集 CPU MIDR/容量、policy related_cpus、cpuset/uclamp、WALT/PELT 运行状态、thermal pressure、idle residency。负载包括 UI 冷/热启动、滚动、游戏渲染、后台编译/下载、多任务内存压力。以同版本、相同 Root 模块、同刷新率和环境温度做配对 ABBA、每负载至少 5 对，固定时长和电量区间。报告 p50/p95/p99 runnable 延迟、帧时间和 jank、迁移数、idle residency、同工作量能耗、热峰值与吞吐。异常温度/负载重跑，不挑选最优样本。

`scripts/analyze_ab.py` 读取真实配对 CSV 并拒绝 NaN、重复/缺失配对和明显不一致的时长/电量。它只做描述性比较，不声称显著性。无真实 CSV 时不生成实机性能报告。EEVDF/sched_ext/GPU 表均未修改。
# 补充：编译证据

`scripts/build-object-probes.sh` 已在独立输出目录使用锁定 Clang 与历史 ACK 5.15 头文件编译 vas_core.o/vas_probe.o；主机 GCC 静态检查通过。见 `evidence/object-probes-result.json` 和对应日志。仍未注册调度 hook，不能称为已替换/优化了手机调度器。

