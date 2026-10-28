// SPDX-License-Identifier: GPL-2.0-only
/* Compile-only kernel API probe. No hook registration or scheduling mutation.
 * Not installed/loaded. Core decision algorithm is shared with host tests. */
#include <linux/module.h>
#include "vas_core.h"
static int __init vas_probe_init(void)
{
    struct vas_state state={0};
    vas_update(&state,256,1000);
    if (state.util_ewma!=256) return -EINVAL;
    pr_info("VAS research core: observation only, no scheduler hook registered\n");
    return 0;
}
static void __exit vas_probe_exit(void) {}
module_init(vas_probe_init);
module_exit(vas_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VAS research core compile probe; not a production scheduler");
