# Reusable hero debug console / 通用英雄调试指令

生成器会复制 `mod/scripts/hero_debug.lua`。它是通用解析模块，不直接修改任何英雄的存档或属性；新英雄须按下方接入游戏逻辑。狗头工程已实际接入并测试。模板的剑魔参考没有蓝条，不会因为复制模块而自动获得无限蓝功能。

统一命令优先使用 lol 前缀；旧的英雄前缀仍可使用：

| Command | 中文 | English |
|---|---|---|
| `nasus help` | 查看通用命令 | Show commands |
| `nasus level 18` | 设置为 18 级，不自动加点 | Set level; spend skill points yourself |
| `nasus 0cd on` / `off` | 开启 / 关闭零冷却 | Enable / disable zero cooldown |
| `nasus mana on` / `off` | 开启 / 关闭无限蓝 | Enable / disable infinite mana |
| `nasus gold 99` | 将金币设为 99 | Set coins to 99 |
| `nasus gold add 20` | 增加 20 金币 | Add 20 coins |

`0cd` 和 `mana` 不带 on/off 时切换开关。金币受游戏本身的持币上限约束，输出实际金币数。等级和金币写入正常游戏存档；调试开关只保存在当前运行状态，退出继续游戏后关闭。降级时必须重新校验技能等级上限；不得复制装备、被动叠层或物品。

## 接入 / Integration

在已有 `MC_EXECUTE_CMD` 回调之前创建解析器，在回调最前面分发。不要重复注册会执行同一命令的处理器。以下名称代表英雄自己的游戏模块：

```lua
local debugConsole=include('scripts.hero_debug').new({
    prefix='yourhero', maxLevel=18, supportsMana=true,
    getPlayer=function()
        if game:GetNumPlayers()>0 then return Isaac.GetPlayer(0) end
    end,
    isHero=isYourHero, state=state, save=function()saveProgress()end,
    setLevel=function(p,n)
        -- Implement this in your progression module: preserve stacks/items,
        -- reset current XP, clamp skill ranks, sync HP/mana growth and skill points.
        return Progress.setLevel(p,n)
    end,
    gold=function(p,n,adding)
        Equipment.addGold(p,adding and n or n-p:GetNumCoins())
        return p:GetNumCoins()
    end,
    onFlag=function(p,key,enabled)
        local s=state(p)
        if key=='noCD' and enabled then
            for _,skill in ipairs({'q','w','e','r'}) do s[skill..'Ready']=s.clock end
        elseif key=='infiniteMana' and enabled then
            -- Fill the hero's authoritative mana here.
            Abilities.resource(p)
        end
    end,
})
mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD,function(_,command,args)
    if debugConsole(command,args) then return end
    -- Existing hero-specific commands follow.
end)
```

技能支付逻辑还必须读取 `state(p).noCD` / `state(p).infiniteMana`：零冷却跳过时间检查并令新冷却为零；无限蓝在资源读取时补满且支付时不扣除。不绕过技能未学习、死亡、动作阶段等正常规则。没有蓝条时设 `supportsMana=false`；不要仅显示 ON 却不修改实际支付逻辑。

The shared lol aliases silently ignore inactive heroes; keep the unique hero prefix as a legacy alias. The parser validates integer ranges and toggle arguments, checks the active hero, and delegates every mutation to the adapter. The parser itself does not register engine callbacks or implement champion mechanics. Missing handlers report unsupported commands. Test the adapter's real payment, progression and save paths, not just parser output.

## Shared aliases / 无需替换英雄名

`lolgold 99`, `lollevel 16`, `lolheal`, `lolrespec`, `lolcd on/off`, `lolresource 100`, `lolstatus`, `lolhelp`; mana heroes also support `lolmana on/off`.

The adapter must supply heal(p, amountOrNil), respec(p), resource(p, amount), status(p) as well as setLevel/gold/onFlag. Respec refunds all spent skill points. Clamp resource to the hero's resource cap; never create mana for manaless heroes. Only the active hero handles shared aliases, avoiding duplicate mutations/output. Include CONSOLE-COMMANDS.txt in the release and common commands in the final reply.
接好实际回血、洗点、资源、状态函数；洗点退还所有技能点，无蓝英雄不凭空创建法力。成品和最终回复必须告诉玩家常用指令。
