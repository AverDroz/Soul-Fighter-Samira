# 资源回复与弹速 / Resource recovery and shot speed

生成器会复制 `tools/hero_balance.lua` 到新英雄的 `mod/scripts/hero_balance.lua`。已有项目可以复制同一模块并接入自己的资源更新；仅复制文件不会自动改变英雄机制。

统一规则：持续回蓝 = 英雄原本回蓝 × 3 × `player.ShotSpeed`。弹速 1.0 是基准，1.5 表示回复速度再乘 1.5；基础、等级和装备回蓝先汇总，再计算一次。暂停时不推进，最终限制到最大法力。一次性回蓝、消耗和上限不乘此倍率；无蓝英雄不添加蓝条。

```lua
local Balance=include('scripts.hero_balance')
-- Once per 30 Hz gameplay tick, not per render/player callback:
mana=math.min(maxMana,mana+Balance.manaRegenPerTick(totalManaRegenPerFiveSeconds,player.ShotSpeed))
```

怒气保留该英雄原本的基础获取量，仅按弹速缩放。持续获得怒气使用每秒基础值；攻击等事件产生怒气时按单次基础值计算。两条路径不要对同一次获取重复使用，怒气消耗、衰减和上限不改。

```lua
rage=math.min(maxRage,rage+Balance.rageRegenPerTick(baseRagePerSecond,player.ShotSpeed))
-- OR, once on a successful rage-generating event:
rage=math.min(maxRage,rage+Balance.resourceGain(baseRagePerHit,player.ShotSpeed))
```

每次读取当前弹速，拿取/出售道具和 rewind 后自动使用恢复后的属性，不缓存额外倍率。函数返回小数，不要按整数截断。没有蓝量/怒气系统的英雄仍需自行实现资源状态、HUD、存档和回退。

English: continuous mana regeneration is the champion's normal rate × 3 × Isaac `ShotSpeed` (1.0 is neutral). Sum base, growth and item regen first; call `manaRegenPerTick(perFiveSeconds,shotSpeed)` once per 30 Hz gameplay tick. Clamp to maximum mana and do not advance while paused. Do not scale instant mana restores, costs or capacity, or add mana to manaless heroes.

Rage retains its champion-specific base rate and receives only the shot-speed multiplier. Use `rageRegenPerTick(perSecond,shotSpeed)` for continuous gain, or `resourceGain(perEvent,shotSpeed)` once per successful rage-generating event. Never apply both to the same gain. Costs, decay and capacity are unchanged. Read current shot speed each time, retain fractional values, and implement the hero's own resource state/HUD/save/rewind integration. Copying this helper alone does not implement a resource system.
