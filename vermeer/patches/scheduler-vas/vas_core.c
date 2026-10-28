/* SPDX-License-Identifier: GPL-2.0-only */
#include "vas_core.h"

void vas_update(struct vas_state *s, unsigned int util, unsigned int wait_us)
{
    if (!s || util > 1024 || wait_us > 1000000) return;
    if (!s->samples) { s->util_ewma=util; s->wait_ewma=wait_us; }
    else {
        s->util_ewma=(s->util_ewma*7+util)/8;
        s->wait_ewma=(s->wait_ewma*7+wait_us)/8;
    }
    if (s->samples != ~0U) ++s->samples;
}

struct vas_result vas_select(const struct vas_cpu *cpus, unsigned int n,
                            const struct vas_profile *p, const struct vas_task *t)
{
    struct vas_result out={-1,0,3,0};
    vas_u64 best=~(vas_u64)0, previous=best, ids=0;
    unsigned int i, effective, load, can_apply;
    if (!cpus || !p || !t || !n || n>64 || t->util>1024 || t->wait_us>1000000 ||
        t->interactive>1 || t->prev_cpu>=64 || t->now_us<t->last_migration_us ||
        !p->latency_budget_us || p->latency_budget_us>1000000 ||
        p->migration_hold_us>1000000 || p->improvement_permille>1000 ||
        !p->energy_weight || p->energy_weight>1000 || !p->latency_weight ||
        p->latency_weight>1000 || p->observe_only>1) return out;
    for (i=0;i<n;++i) {
        const struct vas_cpu *c=&cpus[i];
        if (c->id>=64 || c->kind>VAS_X3 || !c->capacity || c->capacity>1024 ||
            c->thermal_pressure>c->capacity || c->util>1024 ||
            !c->energy_cost || c->energy_cost>4096 || c->online>1 ||
            (ids & ((vas_u64)1<<c->id))) return out;
        ids|=(vas_u64)1<<c->id;
    }
    for (i=0;i<n;++i) {
        const struct vas_cpu *c=&cpus[i];
        vas_u64 score, demand;
        if (!c->online || !(t->allowed_mask & ((vas_u64)1<<c->id))) continue;
        effective=c->capacity-c->thermal_pressure;
        if (!effective || t->util>effective) continue;
        load=c->util+t->util;
        /* Convex contention term penalizes packing and preserves room for other
         * tasks. This is a heuristic cost, NOT measured watts or a deadline. */
        demand=(vas_u64)load*1024/effective;
        score=(vas_u64)c->energy_cost*p->energy_weight +
              demand*demand*p->latency_weight/1024;
        if (t->interactive && t->wait_us>p->latency_budget_us)
            score+=demand*(t->wait_us/p->latency_budget_us)*p->latency_weight;
        /* X3 receives no unconditional boost. A710/A715 remain separate kinds
         * and receive their individually calibrated energy/capacity inputs. */
        if (c->id==t->prev_cpu) previous=score;
        if (score<best || (score==best && c->id==t->prev_cpu)) {
            best=score; out.cpu=(int)c->id;
        }
    }
    if (out.cpu<0) { out.reason=4; return out; }
    out.reason=0;
    if ((unsigned int)out.cpu!=t->prev_cpu && previous!=~(vas_u64)0) {
        if (t->now_us-t->last_migration_us<p->migration_hold_us) {
            out.cpu=(int)t->prev_cpu; best=previous; out.reason=1;
        } else if ((previous-best)*1000 < previous*p->improvement_permille) {
            out.cpu=(int)t->prev_cpu; best=previous; out.reason=2;
        }
    }
    can_apply=!p->observe_only;
    out.may_apply=can_apply; out.score=best;
    return out;
}
