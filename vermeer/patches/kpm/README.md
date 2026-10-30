# KPM 调查状态

对应官方源码 `SukiSU-Ultra/SukiSU_KernelPatch_patch@bc2bf170c3251a849ecf52e98ff66b6df7160415`，归档及 SHA-256 provenance 在 `evidence/upstream-research/kpm-source.tar.gz` 旁。

当前未执行任何 Image 二进制 patch，没有自动加载模块。SukiSU 自带的 KPM 控制/占位接口代码被编译不表示完整框架已激活。正式集成还需锁定 patcher 源码与可复现工具、检验未修补输入/单次输出身份、签名和版本校验、CFI/KMI 兼容，以及独立禁用与恢复路径。不会下载移动分支二进制后直接执行或把 CONFIG_KPM=y 当作功能验证。
