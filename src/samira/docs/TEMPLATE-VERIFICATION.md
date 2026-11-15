# 模板 1.0.0 验证记录

日期：2026-11-02。参考 Mod 0.7.54，运行时基线 Companion 0.7.53。

已完成：

- 从模板生成独立 ID `templateprobe` 项目；核对 431 个转换后的源码文件与生成器输出一致。
- 身份生成测试：拒绝目录穿越、Windows 保留名、已有剑魔 ID 和已存在输出目录；不同 ID 得到不同通信/安装标识；源目录不修改。
- 保留原始 GLB 片段名和粒子 JSON，避免全局替换破坏动画。
- 生成项目完整 Lua 行为测试、549 个动画资源检查、音频文件与原有素材哈希检查通过。
- 生成项目的 9 项通信测试、9 项安装器生命周期测试通过（使用临时假游戏目录，不修改玩家安装）。
- 生成项目离屏 GPU 模型与 Q 命中特效检查通过，测试显卡为 RTX 5080；这不是实际游戏帧率保证。
- 编译生成项目专属 x86 DLL、Windows 安装维护界面，并打包完整 Companion。
- 使用该包自带的隔离 Python 运行离屏渲染自检，校验全部 1389 个 payload 文件通过。
- 发布源码扫描没有原作者用户目录、Codex runtime 路径或旁边 Minecraft Mod 的隐式依赖。

未完成/不应声称已完成：

- 尚无第二个真正适配完成的英雄；`templateprobe` 仍使用剑魔素材和机制。
- 未将临时英雄安装到玩家的实际游戏中进行完整游玩。
- 未验证多个外部英雄同时启用、同屏多人、Linux/Steam Deck。
- 未实现多英雄共用一个渲染进程的通用插件宿主。

后续 Agent 应按 docs/VALIDATION.md 对自己的英雄重新验证。模板测试通过不等于它新增的技能或素材已经通过。

## 2026-11-14 / source template 1.0.4
Scoped Mother phase-2 camera, mirror presentation/input separation and retained knock-up userdata are integrated. See RUNTIME-PITFALLS.md for conditional summon/save/rewind, shop, healing and release lessons. Camera/mirror/lift Lua mocks, Lua syntax, generator tests and refreshed-export hash regression passed. No live game verification. Source-only reference still requires champion implementation and original assets. Existing Companion protocol unchanged.
