# 给其他玩家的 Agent：请从这里开始

目标：复用已经解决的以撒与外部渲染接入问题，把工作集中在新英雄身上。
本文件既适用于模板根目录，也会复制到生成的新英雄项目中。

## 先识别你在哪

- 有 `example/`、没有 `hero.json`：这是模板。先读玩家需求，选一个独立 ID，用 `tools/new_hero.py` 生成**模板目录之外的新目录**。
- 有 `hero.json`、`mod/`、`external/`：这是可编辑项目。读取身份记录；不要再次全局重命名。
- 只有游戏的 `mods` 文件夹：先解压开发模板到普通工作目录，不要把玩家的存档/安装目录当源码仓库。

`hero.json` 记录生成时的身份和发布版本。当前它不是运行时配置文件：修改 ID/name 不会自动重命名代码；需要重新生成或进行完整迁移。`version` 用于 `tools/build_release.py` 的发布版本，应与 Mod metadata/遥测版本同步维护。

## 开工前确认的最少信息

询问/查找：目标英雄及皮肤、可用模型/动画/语音/特效素材、游戏路径、是否继续沿用现有商店/经验/数值生命体系。不要要求玩家把整个 LoL 客户端上传到聊天；本地素材目录即可。
若没有英雄素材，先做素材清单和逻辑原型，明确显示仍是剑魔参考外观。不要编造已提取的动画或宣称全部粒子都支持。

先阅读：

1. [架构与通信](docs/ARCHITECTURE.md)
2. [新英雄适配路径](docs/PORTING.md)
3. [验证要求](docs/VALIDATION.md)
4. [打包和安装](docs/RELEASE.md)

生成后先运行 `tools/check_project.py`、`tools/test.py`，记录基线。原版粒子和动画 JSON 内出现 `aatrox` 是允许的；角色注册名、脚本模块名和通信标识仍使用剑魔则是隔离失败。

## 三层职责不能混淆

音效与资源条也属于英雄适配：检查普攻、被动、Q/W/E/R 的施放、命中、蓄力/就绪、持续、结束音效及技能语音；如亚索 Q3 蓄风与 R 连斩、落地、喊话。核对原版素材可解码、注册名、实际触发及语音优先级，循环音效在消耗/到期/死亡/换房/退出时停止。缺少事件明确说明，不能仅以“文件存在”判定完成。

资源按英雄规则接入 Lua，并在 HUD 和头顶血条下显示实际资源条（数值/上限、颜色、空/满、获取/消耗、重置及读档一致）。无蓝英雄不加蓝条，但剑意等特殊资源仍需显示，不能只在被动图标写数字。做一次简短声音/资源检查即可；不能运行游戏时注明待玩家试听和试玩，不要求截图或录像。

Audio/resource integration: check original attack/passive/Q/W/E/R cast, impact, charge/ready, sustain, end SFX and ability voices, including special stages (e.g. Yasuo Q3-ready wind and R slashes, landing and shout). Verify decoding, registration, actual runtime triggers and voice priority. Stop loops on consumption, expiry, death, room change and exit; file presence alone is insufficient.

Lua owns resource values. Render the actual resource under health in both the HUD and overhead display, with matching current/max, colors, empty/full, gain/spend, reset and load behavior. Manaless heroes receive no invented mana; special resources such as Flow still need a bar. Keep checks short; if the game cannot run, mark listening/playtesting pending. No screenshots or video required.

通用调试命令模块和接入示例见 [DEBUG-CONSOLE.md](docs/DEBUG-CONSOLE.md)。生成器会复制 `hero_debug.lua`；移植英雄时须接入实际等级、冷却、法力与金币逻辑，不能只复制文件就声称功能已启用。

| 层 | 工作 | 主要入口 |
|---|---|---|
| 游戏 Lua | 输入、导航、技能命中、伤害、数值生命、装备、经验、保存 | `mod/main.lua`、`mod/scripts/<id>_*.lua` |
| 外部渲染 | 模型动画、粒子、HUD、视觉鼠标；只消费快照 | `external/overlay.py`、`model.py`、`combat_effects.py`、`hud.py` |
| Companion | REPENTOGON 启动桥、等待角色、管理渲染子进程、安装维护 | `companion/bridge.c`、`companion.py`、`installer.py`、`Setup.cs` |

游戏逻辑仍在以撒里。外部窗口透明覆盖游戏客户区，不是替换了以撒引擎，也没有读取 LoL 运行内存或连接 LoL 客户端。

## 推荐实现顺序

统一资源规则：持续回蓝为原设定的 3 倍，再乘以撒弹速（1.0 为基准）；怒气获取保留英雄自身基础值，再乘弹速。生成器自带 `mod/scripts/hero_balance.lua`，按当前属性计算，不重复乘倍率、不影响一次性回蓝或资源消耗。接入代码、单位和存档注意事项见 [资源回复与弹速](docs/RESOURCE-BALANCE.md)。

1. **基线与身份**：生成项目，测试通过；保持剑魔例子能运行，先不改所有系统。
2. **模型与动画**：idle/walk/attack/death，骨骼与材质、武器挂点、体型/朝向，再接技能动画。
3. **英雄机制**：逐个实现被动/Q/W/E/R，先确定范围、时序、目标规则及伤害再接特效。角色有资源条时再加蓝量/能量；不要套用剑魔无蓝机制。
4. **素材与反馈**：接原版粒子/语音/图标，完成语言切换。范围指示器和 Lua 判定共用几何数据，避免看起来命中但实际没伤害。
5. **以撒兼容**：原生攻击属性、道具、飞行、原生回血/受伤、主动/卡牌/炸弹、rewind、复活、转场。
6. **发布**：测试并打包新英雄自己的 Companion，使用明确的用户游戏路径安装；最后再做游戏内验收。

每次报告要区分“完成了机制”“接好了素材”“通过模拟/离屏检查”“玩家或 Agent 在实际游戏验证”。不要把改名、语法通过或截图一张等同于全英雄完成。

## 已踩过的坑

- 不要让 60 Hz 的玩家回调把 30 Hz 技能计时推进两次；原生无敌帧的单位另行核对。
- 原生门负责房间转移。不要用重建房间/重载楼层的方式修过门，可能刷新怪物/道具。
- 伤害应在接受命中后结算；回血保留小数，不强行折回半心。装备出售/撤回要还原真实道具和衍生物。
- 飞行必须改变路径可通行判定，不能只换飞行动画。
- 新房间不得插值上一房间的坐标；暂停/黑屏/CG/活板门要按场景让出外部人物绘制。
- 不要反复隐藏/显示置顶窗口来处理普通房间切换，否则可能造成全屏切换和 HUD 闪烁。
- 普通输入和反复移动指令不能抢占高优先级台词；角色专属语音优先级需要明确规则。
- 本工程不通用支持任意 GLB：骨骼名称、128 骨骼上限、材质分件、动画插值、挂点均要检查。
- 粒子适配器不支持所有 LoL 渲染特性，复杂网格/场景深度/折射需要单独实现。缺失就说明，不能悄悄画一个替代。

## 给玩家的交付

提供新英雄 Mod 文件夹、对应 Companion ZIP、安装/更新方法、操作说明和实际验证结果。玩家照常从 REPENTOGON 启动器进游戏，不应需要 Codex、开发 Python 或手动执行控制台命令。

目前模板是独立分支方案，不是共享多英雄宿主。不得让两个英雄使用同一个 DLL/INI/日志前缀/握手目录。虽然生成器已隔离这些标识，**多 Mod 同时启用与多人绘制仍需实际测试**。未来如改共享宿主，应建立显式 `heroId` 路由和单一渲染所有者，不能通过互相覆盖安装目录实现。

English handoff: read hero.json, validate the untouched example, then port one feature at a time. Lua owns gameplay; Python owns visuals; Companion owns lifecycle. Keep original animation names intact, maintain scene ownership/fallback, and never claim a generated Aatrox clone is a completed champion. Read the four linked documents for concrete file mappings and release commands.

## 新英雄适配默认 / New hero defaults
新开局 3 级、3 个待分配技能点，不自动学 Q；继续存档不重置。生成选人肖像/名字并检查 content/gfx 的图片引用。按游戏内坐标校准模型尺寸、回退模型和脚底；不继承其他英雄的残影。按源数据换算资源公式、粒子单发/颜色查表/坐标绑定。接入 docs/DEBUG-CONSOLE.md 的 lol 通用指令，并在成品包和最终回复给玩家指令说明。检查保持简短，无游戏环境则明确待试玩。
Start new runs at level3 with3 unspent points and no automatic Q. Preserve continued saves. Generate and validate menu images, calibrate model/fallback/feet in game units, and do not inherit another champion's ghosts. Honor source resource units and particle count/color/coordinate bindings. Integrate shared lol commands and document them in both the release and final reply. Keep checks brief and report if live playtesting remains.

选人素材使用 Studio 导出的 generated/portraits/select.png、page.png，按 layout.json 的 100% 缩放和脚底轴心接入。front.png 仅作正面高清参考；不能将透明边裁掉再撑满画布。角色名字和称号须更新。人形身体先以 36–44 游戏逻辑像素（脚底到头，排除武器/头发）校准。
Use Studio exported generated/portraits/select.png and page.png at the layout.json pivot and 100% scale; retain padding. front.png is a front-facing reference, not a full-size roster sprite. Update the name/title. Calibrate humanoid bodies at 36–44 logical pixels feet-to-head, excluding weapons/hair.

玩家包 ZIP 顶层只放实际 <hero>_isaac 文件夹，INSTALL.txt、CONSOLE-COMMANDS.txt、Companion.zip 与 main.lua 同级；不用发布名称/版本再包一层。可用 tools/package_player.py 构建并验证。商店全部白名单装备都应可滚轮浏览和购买，格子和点击由 Lua 统一计算。
Player ZIP: only <hero>_isaac at the top level, containing main.lua, INSTALL.txt, CONSOLE-COMMANDS.txt and the Companion ZIP. No release/version wrapper. Use tools/package_player.py to build and validate. Every allowed shop item must remain reachable and purchasable via scrolling; Lua owns both layout and hitboxes.


content/items.xml 即使只注册复活用的 null 效果，根节点也必须写成 <items gfxroot="gfx/items/" version="1">，不能省略 version 或 gfxroot；缺少 version 会在 Lua 加载前导致原生崩溃。
Even a null-only content/items.xml must use <items gfxroot="gfx/items/" version="1">. Do not omit version or gfxroot; missing version crashes the native loader before Lua runs.
最终成品打包和安装脚本会自动运行资源检查，检查失败必须修正后再交付，不要跳过检查。
The final player packager and mod installer run resource checks automatically; fix failures before delivery rather than bypassing the check.

Read docs/RUNTIME-PITFALLS.md before adapting camera, mirror coordinates, knock-up, summon/save/rewind, shop or release behavior. Preserve existing Companion compatibility; do not silently require players to reinstall it.

黑屏兼容接入与构建检查见 docs/RELEASE.md 的“黑屏兼容模式”。不要只添加 displayModes 声明而遗漏渲染循环。
