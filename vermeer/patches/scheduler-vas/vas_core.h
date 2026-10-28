/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef VERMEER_VAS_CORE_H
#define VERMEER_VAS_CORE_H
#ifdef __KERNEL__
#include <linux/types.h>
typedef u64 vas_u64;
#else
#include <stdint.h>
typedef uint64_t vas_u64;
#endif
enum vas_kind { VAS_A510, VAS_A710, VAS_A715, VAS_X3 };
/* util/capacity: scheduler scale 0..1024. energy_cost: calibrated relative
 * cost 1..4096, NOT inferred from the core name or CPUFreq policy number. */
struct vas_cpu {
    unsigned int id, kind, capacity, thermal_pressure, util, energy_cost;
    unsigned int online;
};
struct vas_profile {
    unsigned int latency_budget_us, migration_hold_us, improvement_permille;
    unsigned int energy_weight, latency_weight, observe_only;
};
struct vas_task {
    unsigned int util, wait_us, interactive, prev_cpu;
    vas_u64 allowed_mask, now_us, last_migration_us;
};
struct vas_state { unsigned int samples, util_ewma, wait_ewma; };
struct vas_result { int cpu; unsigned int may_apply, reason; vas_u64 score; };
/* reason: 0 best/keep, 1 hold, 2 marginal improvement, 3 invalid inputs,
 * 4 no feasible CPU. Caller must fall back to original scheduler on errors. */
void vas_update(struct vas_state *, unsigned int util, unsigned int wait_us);
struct vas_result vas_select(const struct vas_cpu *, unsigned int count,
                            const struct vas_profile *, const struct vas_task *);
#endif
