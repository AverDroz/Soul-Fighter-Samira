# 从剑魔例子适配新英雄

表中 `<id>` 是生成的项目 ID。不要一次删除全部剑魔代码；先建立基线，再按功能替换。

| 要改的内容 | 主要文件 | 必须核对 |
|---|---|---|
| 注册、肖像、选人、教程 | `mod/content/players.xml`、`mod/content/gfx`、`<id>_branding.lua` | 内部名与角色菜单动画一致；图片仍是剑魔占位 |
| 输入与移动 | `<id>_controls.lua`、`<id>_navigation.lua`、`main.lua` | 鼠标/WASD/手柄，原生丢弃/切换，飞行和门 |
| Q/W/E/R、普攻和被动 | `main.lua`、`<id>_abilities.lua`、`<id>_geometry.lua`、`<id>_passive.lua` | 时序、目标锁定、取消规则、范围、攻速与技能极速 |
| 成长、资源与生命 | `<id>_progression.lua`、`<id>_health.lua` | 当前是剑魔数字 HP；蓝量/能量没有通用实现 |
| 装备、存档与 rewind | `<id>_equipment.lua`、`<id>_item_effects.lua`、`<id>_rewind.lua`、`main.lua` | 新状态需加入保存/恢复；撤回不能复制属性/回血 |
| 原生武器/地形联动 | `<id>_q_weapons.lua`、`<id>_terrain.lua` | 现有全部以剑魔 Q 为中心，不适合无脑复用 |
| 动画和分件 | `external/model.py`、`reference/source/model.glb`、`<id>_animation_data.lua`、`<id>_external_actions.lua` | `CLIPS`、`visible_parts`、Pelvis/Root、武器挂点、128 joints 上限 |
| 语音和音乐 | `<id>_audio.lua`、`<id>_music.lua`、`content/sounds.xml`、`music.xml` | 中英原版音频、时长、语音优先级、Boss 专属台词应重新选 |
| 特效和指示器 | `external/combat_effects.py`、`client_vfx.py`、`external/assets/client` | 粒子材质和支持特性、挂点、单位比例；不是贴上图片就等于原版 |
| HUD、商店与提示 | `<id>_hud.lua`、`external/hud.py`、`shop_ui.py`、`localization.py` | 图标/文本、冷却、资源条、中文英文长文本、点击区域与显示一致 |
| 回退素材 | `<id>_fallback.lua`、`<id>_visuals.lua`、`mod/resources/gfx/<id>` | 外部未就绪时有体积小的可用角色，切换不叠画 |

## 素材导入

先列出文件及动画目录，确认素材不是只有静态模型。当前 `Model` 接受 GLB，使用 TRS、LINEAR/STEP 动画、单套选定 skin；其他 rig/多 skin/CUBICSPLINE 需要显式支持。

`tools/export_external_actions.py` 从 GLB 列出动作并生成 Lua 时长表。先修改 `model.py` 中剑魔绑定假设，再运行它。
`bake_model.py` / `bake_combat.py` / `bake_smooth.py` 是旧版精灵烘焙参考；它们仍包含剑魔分件、角度和动作假设，不要为了外部模型默认重烘全部序列帧。只在需要 native fallback 时调整相应动作。

完整原版粒子还需要客户端的事件配置、贴图、网格和资源映射。模板包含已适配剑魔和心之钢的运行数据，不包含整个 LoL 解包工具链。若用户有客户端，选择需要的文件提取即可；保留来源及映射记录，不把机器绝对路径写入发布代码。

## 技能实现小样

例如新英雄 Q 是直线弹道：Lua 负责起点、方向、速度、寿命、命中和伤害；快照发送弹道 ID/位置/年龄；Python 根据这个数据绘制特效。Python 不另开一套碰撞系统，也不按渲染 FPS 推进技能冷却。

新英雄多段技能不一定符合现有 `Q1/Q2/Q3` 数据。应在 Lua 和渲染侧一起修改协议载荷/动作映射，并为未识别状态提供明确回退。不要为了保留旧字段把不同英雄技能硬塞进剑魔 W 锁链或 R 翅膀规则。

当前调参仅是参考：多 Q 同目标额外命中 50%、剑魔 E 吸血、大灭回血、被动和三段 Q 地形联动，都不是通用框架规则。
