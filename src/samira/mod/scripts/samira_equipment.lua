local Stasis=include('scripts.samira_stasis')
local Health=include('scripts.samira_health')
local Balance=include('scripts.samira_balance')
-- Shop transactions and six slots are authoritative in Lua, never in the overlay.
local E={items={},keys={1,2,3,5,6,7}}
for _,item in ipairs(include('scripts.samira_shop_catalog')) do E.items[item.id]=item end
local function number(n,default,maximum)
    return type(n)=='number' and n==n and n>=0 and math.min(maximum or 1000000,math.floor(n)) or default
end
local savedFields={'heal','damageBank','heartsteel','stacks','bloomReady','potionUntil','potionRate','elixirUntil','elixir','shield','shieldUntil','spellblade','speedUntil','stasis','rebirth','energized','attacks','combatUntil','combatTicks','lastHurt','overdrive','empower','storm','tear','rodTime','hungerUntil','hubris','hubrisUntil','debt','debtUntil','cullKills','supportGold','petKills','forceStacks','forceUntil','yuntal','soulStacks','soulKills','supportBuff','terminus','terminusUntil','vowUntil','ironUntil','hat','circlet','rage','rageUntil','pipesUntil','sabotage','bootKills'}
savedFields[#savedFields+1]='youmuuUntil'
local function empty()return {id=0,count=0,ready=0,charges=0}end
function E.native(id)
    if not Isaac.GetItemConfig then return end
    local item=Isaac.GetItemConfig():GetCollectible(id)
    if not item or item.Type==ItemType.ITEM_ACTIVE then return end
    -- Progression items belong to Isaac, not the six-slot equipment economy.
    -- The native quest tag covers key/knife pieces and other route components,
    -- including tagged modded items. Never remove ownership or spawn a pedestal.
    if ItemConfig and ItemConfig.TAG_QUEST and item:HasTags(ItemConfig.TAG_QUEST) then
        E.items[-id]=nil;return
    end
    local key=-id
    local name=item.Name or ('Item '..id)
    local english=name:gsub('^#',''):gsub('_NAME$',''):gsub('_',' ')
    if name:sub(1,1)=='#' and Isaac.GetString then name=Isaac.GetString('Items',name:sub(2)) end
    local description=item.Description or ''
    if description:sub(1,1)=='#' and Isaac.GetString then description=Isaac.GetString('Items',description:sub(2)) end
    E.items[key]={id=key,name=name,english=english,price=0,sell=item.Quality or 0,stats={},components={},buyable=false,stack=1,
        category='原生',native=id,gfx=item.GfxFileName,description=description,adaptation='以撒被动道具，保留原有效果。出售获得品质对应的金币。'}
    return E.items[key]
end
function E.free(p)
    for i,a in ipairs(E.state(p).slots) do if a.id==0 then return i end end
end
function E.refreshNative(p)
    -- Rebuild stats, weapon effects and item-owned familiars from remaining items.
    p:AddCacheFlags(CacheFlag.CACHE_ALL)
    p:EvaluateItems()
end
function E.syncInventory(p)
    local g=E.state(p);if g.syncing or not p.GetCollectibleNum or not Isaac.GetItemConfig then return end
    g.syncing=true
    local seen={};local removed=false
    for i,a in ipairs(g.slots) do if a.id<0 then
        local id=-a.id;seen[id]=(seen[id] or 0)+1
        if seen[id]>p:GetCollectibleNum(id,true) or not E.native(id) then g.slots[i]=empty();g.dirty=true end
    end end
    local list=Isaac.GetItemConfig():GetCollectibles()
    for id=1,list.Size-1 do
        local count=p:GetCollectibleNum(id,true)
        if count>0 and E.native(id) then
            local used=0;for _,a in ipairs(g.slots) do if a.id==-id then used=used+1 end end
            for n=used+1,count do
                local index=E.free(p)
                if index then g.slots[index]={id=-id,count=1,ready=0,charges=0}
                else
                    -- Preserve surplus old-save/reroll items as pedestals instead of deleting them.
                    p:RemoveCollectible(id,true)
                    removed=true
                    local pickup=Isaac.Spawn(EntityType.ENTITY_PICKUP,PickupVariant.PICKUP_COLLECTIBLE,id,p.Position+Vector(35,0),Vector.Zero,nil):ToPickup()
                    if pickup then pickup.Wait=30 end
                end
                g.dirty=true
            end
        end
    end
    if removed then E.refreshNative(p) end
    g.syncing=false
end
function E.nativePayload(p)
    local result={}
    for _,a in ipairs(E.state(p).slots) do if a.id<0 and E.items[a.id] then result[tostring(a.id)]=E.items[a.id] end end
    return result
end
local function copy(slots)local t={};for i=1,6 do local a=slots[i];t[i]={id=a.id,count=a.count,ready=a.ready,charges=a.charges} end;return t end
function E.restore(p,saved,deferHealth)
    Stasis.clear(p)
    saved=type(saved)=='table' and saved or {};local g={gold=p.GetNumCoins and p:GetNumCoins() or 0,time=number(saved.time,0,1000000000),slots={},grantedHP=number(saved.grantedHP,0,48),kills=number(saved.kills,0),stacks=number(saved.stacks,0)}
    for i=1,6 do local a=type(saved.slots)=='table' and saved.slots[i];local item=type(a)=='table' and (E.items[a.id] or type(a.id)=='number' and a.id<0 and E.native(-a.id))
        g.slots[i]=item and {id=item.id,count=math.max(1,number(a.count,1,math.max(1,item.stack))),ready=number(a.ready,0,1000000000),charges=number(a.charges,2,4)} or empty()
    end
    for _,key in ipairs(savedFields) do local v=saved[key];if type(v)=='number' and v==v and v>=0 and v<1000000000 then g[key]=v end end
    if saved.elixir=='wrath' or saved.elixir=='sorcery' then g.elixir=saved.elixir end
    if type(saved.redemption)=='table' and type(saved.redemption.x)=='number' and type(saved.redemption.y)=='number' and type(saved.redemption.at)=='number' then g.redemption={x=saved.redemption.x,y=saved.redemption.y,at=saved.redemption.at} end
    g.cooldowns={};if type(saved.cooldowns)=='table' then for k,v in pairs(saved.cooldowns) do if type(k)=='string' and #k<40 and type(v)=='number' and v==v and v>=0 and v<1000000000 then g.cooldowns[k]=v end end end
    -- Preserve an already-running Ghostblade active from pre-0.7.92 saves.
    if not g.youmuuUntil then for _,slot in ipairs(g.slots) do
        if slot.id==3142 and slot.ready-g.time>1680 and slot.ready-g.time<=1800 then
            g.youmuuUntil=math.min(g.speedUntil or 0,slot.ready-1680)
            if g.youmuuUntil>g.time then g.speedUntil=nil end
        end
    end end
    -- Removed shop gear must not leave potion, stasis, shield or temporary stat effects behind.
    for _,key in ipairs({'stasis','shield','shieldUntil','ironUntil','elixirUntil','potionUntil','redemption','overdrive','empower','storm','rebirth','hat','hungerUntil','forceUntil','supportBuff','terminusUntil','vowUntil'}) do g[key]=nil end
    -- Per-target cooldowns survive save/continue and room rewind, without entity references.
    g.heartsteelTargets={}
    for key,v in pairs(type(saved.heartsteelTargets)=='table' and saved.heartsteelTargets or {}) do
        if type(key)=='string' and #key<100 and type(v)=='table' then
            g.heartsteelTargets[key]={charge=number(v.charge,0,90),seen=number(v.seen,0,1000000000),ready=number(v.ready,0,1000000000),stageAt=number(v.stageAt or saved.time,0,1000000000)}
        end
    end
    p:GetData().SamiraGear=g;E.syncInventory(p);if not deferHealth then E.syncHealth(p) end;return g
end
function E.state(p)
    local g=p:GetData().SamiraGear or E.restore(p)
    -- Isaac include creates separate module tables: resolve shared native slots
    -- in each consumer (shop/HUD/telemetry), not only the gameplay instance.
    for _,a in ipairs(g.slots) do if a.id<0 and not E.items[a.id] then E.native(-a.id) end end
    return g
end
function E.coinDisplay(p)
    local g=E.state(p);if p.GetNumCoins then g.gold=p:GetNumCoins() end
end
function E.addGold(p,amount,position)
    local g=E.state(p)
    if p.AddCoins then p:AddCoins(math.floor(amount)) end
    E.coinDisplay(p);g.dirty=true
end
function E.syncCoins(p)
    local g=E.state(p);local before=g.gold;E.coinDisplay(p)
    if g.gold~=before then g.dirty=true end
end
function E.save(p)
    local g=E.state(p);local out={gold=g.gold,time=g.time,slots=copy(g.slots),grantedHP=g.grantedHP,kills=g.kills,cooldowns={}}
    for _,k in ipairs(savedFields) do out[k]=g[k] end
    if g.redemption then out.redemption={x=g.redemption.x,y=g.redemption.y,at=g.redemption.at} end
    for k,v in pairs(g.cooldowns or {}) do out.cooldowns[k]=v end
    out.heartsteelTargets={}
    for k,v in pairs(g.heartsteelTargets or {}) do out.heartsteelTargets[k]={charge=v.charge,seen=v.seen,ready=v.ready,stageAt=v.stageAt} end
    return out
end
function E.has(p,id)for _,a in ipairs(E.state(p).slots) do if a.id==id then return true end end;return false end
function E.sum(p)
    local g=E.state(p);local out={};local present={}
    for _,slot in ipairs(g.slots) do present[slot.id]=true;local item=E.items[slot.id];if item then for key,value in pairs(item.stats) do out[key]=(out[key] or 0)+value*slot.count end end end
    local function owned(id)return present[id] end
    out.hp=(out.hp or 0)+(owned(3084) and (g.heartsteel or 0) or 0)
    if owned(2526) or owned(2530) then out.mana=(out.mana or 0)+(g.circlet or 0);out.healPower=(out.healPower or 0)+(out.mana or 0)/10000 end
    if owned(3124) and (g.rageUntil or 0)>g.time then out.attackSpeed=(out.attackSpeed or 0)+(g.rage or 0)*.08 end
    if owned(2524) and (g.pipesUntil or 0)>g.time then out.attackSpeed=(out.attackSpeed or 0)+.2 end
    if owned(3170) then out.ad=(out.ad or 0)+(345+(out.move or 0))*.05 end
    if owned(3008) or owned(3168) then out.omnivamp=(out.omnivamp or 0)+math.min(10,g.bootKills or 0)*.006 end
    if owned(3168) and Health.ratio(p)<=.5 then out.healPower=(out.healPower or 0)+.12 end
    if (g.ironUntil or 0)>g.time then out.hp=out.hp+300;out.tenacity=(out.tenacity or 0)+.25 end
    if (g.terminusUntil or 0)>g.time then local n=g.terminus or 0;out.armor=(out.armor or 0)+n*3;out.mr=(out.mr or 0)+n*3;out.armorPen=(out.armorPen or 0)+n*.05 end
    if (g.supportBuff or 0)>g.time then
        if owned(3504) then out.attackSpeed=(out.attackSpeed or 0)+.25 end
        if owned(6616) then out.ap=(out.ap or 0)+45 end
    end
    if (g.hungerUntil or 0)>g.time then out.omnivamp=(out.omnivamp or 0)+.1 end
    if owned(6657) then local n=math.min(10,math.floor((g.rodTime or 0)/1800));out.hp=out.hp+n*10;out.ap=(out.ap or 0)+n*3;out.mana=(out.mana or 0)+n*30 end
    if owned(3070) or owned(3003) or owned(3004) or owned(3119) or owned(3040) or owned(3042) or owned(3121) then out.mana=(out.mana or 0)+(g.tear or 0) end
    if owned(3004) or owned(3042) then out.ad=(out.ad or 0)+(out.mana or 0)*.025 end
    if owned(3003) or owned(3040) then out.ap=(out.ap or 0)+(out.mana or 0)*.01 end
    if owned(3119) or owned(3121) then out.hp=out.hp+(out.mana or 0)*.08 end
    if owned(1082) then out.ap=(out.ap or 0)+math.min(10,g.soulStacks or 0)*4 end
    if owned(3041) then out.ap=(out.ap or 0)+math.min(25,g.soulStacks or 0)*5 end
    if owned(4633) then out.ap=(out.ap or 0)+out.hp*.02 end
    if owned(4633) and (g.combatUntil or 0)>g.time and (g.combatTicks or 0)>=150 then
        out.omnivamp=(out.omnivamp or 0)+.08
    end
    if owned(3089) then out.ap=(out.ap or 0)*1.3 end
    if owned(6621) then out.ap=(out.ap or 0)+(out.manaRegen or 0)*10;out.healPower=(out.healPower or 0)+(out.manaRegen or 0)*.02 end
    if owned(2517) then out.haste=(out.haste or 0)+(out.ad or 0)*.1 end
    if owned(3032) then out.crit=(out.crit or 0)+math.min(.25,(g.yuntal or 0)*.002) end
    if owned(6697) and (g.hubrisUntil or 0)>g.time then out.ad=(out.ad or 0)+(g.hubris or 0) end
    if (g.elixirUntil or 0)>g.time then if g.elixir=='wrath' then out.ad=(out.ad or 0)+30;out.omnivamp=(out.omnivamp or 0)+.12 else out.ap=(out.ap or 0)+50 end end
    if (g.overdrive or 0)>g.time then out.attackSpeed=(out.attackSpeed or 0)+.3;out.movePercent=(out.movePercent or 0)+.15 end
    if owned(6665) and (g.combatTicks or 0)>=150 then out.armor=(out.armor or 0)*1.3;out.mr=(out.mr or 0)*1.3 end
    if owned(4401) and (g.forceUntil or 0)>g.time and (g.forceStacks or 0)>=8 then out.mr=(out.mr or 0)+70;out.movePercent=(out.movePercent or 0)+.06 end
    return setmetatable(out,{__index=function()return 0 end})
end
function E.syncHealth(p)
    Health.setGear(p,E.sum(p).hp)
    E.state(p).grantedHP=0
end

local exclusive={}
for group,ids in ipairs({{3053,3155,3156,6673,2525},{3077,3074,3748,6698,6631},{3070,3003,3004,3119,3040,3042,3121},{1101,1102,1103,1105,1106,1107},{3865,3866,3867,3869,3870,3871,3876,3877},{3340,3363,3364}}) do for _,id in ipairs(ids) do exclusive[id]=group end end
local function consume(id,slots,seen)
    if seen[id] then return 0 end
    for _,a in ipairs(slots) do if a.id==id then a.count=a.count-1;if a.count==0 then a.id=0 end;return E.items[id].price end end
    local item=E.items[id];if not item then return 0 end
    seen[id]=true;local credit=0
    for _,child in ipairs(item.components) do credit=credit+consume(child,slots,seen) end
    seen[id]=nil;return credit
end
function E.quote(p,id)
    local item=E.items[id];if not item or not item.buyable then return nil,'不可购买' end
    local g=E.state(p);local slots=copy(g.slots);local credit=0
    for _,child in ipairs(item.components) do credit=credit+consume(child,slots,{}) end
    local maximum=math.max(1,item.stack);local destination
    if maximum>1 then for i,a in ipairs(slots) do if a.id==id and a.count<maximum then destination=i;break end end end
    if not destination then for i,a in ipairs(slots) do if a.id==0 then destination=i;break end end end
    if not destination then return nil,'装备栏已满' end
    for _,a in ipairs(slots) do
        if a.id~=0 and ((a.id==id and item.unique) or item.category=='移动' and E.items[a.id].category=='移动' or exclusive[id] and exclusive[id]==exclusive[a.id]) then return nil,'已拥有不可重复购买' end
    end
    local cost=math.max(0,item.price-credit)
    return {cost=cost,credit=credit,slots=slots,destination=destination,item=item}
end
-- Trade receipts are deliberately transient: save/continue and rewind never
-- revive a refund after an item has already benefited gameplay.
local function tradeMark(p)
    local g=E.state(p);local h=Health.state(p);local values={p:GetNumCoins(),p.Position.X,p.Position.Y,h.hp,h.soul,h.nativeBonus,h.growth,h.gear}
    for _,a in ipairs(g.slots) do
        for _,v in ipairs({a.id,a.count,a.ready,a.charges}) do values[#values+1]=v or 0 end
        if a.id<0 then values[#values+1]=p:GetCollectibleNum(-a.id,true) end
    end
    for _,method in ipairs({'GetCollectibleCount','GetNumBombs','GetNumKeys','GetHearts','GetSoulHearts','GetEffectiveMaxHearts','GetBrokenHearts','GetEternalHearts','GetGoldenHearts','GetBlackHearts'}) do
        if p[method] then values[#values+1]=p[method](p) end
    end
    for _,method in ipairs({'GetCard','GetPill','GetActiveCharge','GetBatteryCharge','GetActiveItem','GetTrinket'}) do
        if p[method] then for slot=0,1 do values[#values+1]=p[method](p,slot) end end
    end
    return table.concat(values,':')
end
function E.clearUndo(p)E.state(p).undo=nil end
function E.canUndo(p)
    local g=E.state(p);local history=g.undo;local last=history and history[#history]
    if not last then return false end
    local s=p:GetData().Samira or {}
    if p:IsDead() or s.cast or s.dash or tradeMark(p)~=last.after then g.undo=nil;return false end
    return true
end
local function beforeTrade(p)
    E.canUndo(p)
    return {slots=copy(E.state(p).slots),gold=p:GetNumCoins(),health=Health.save(p),nativeMax=p:GetEffectiveMaxHearts()}
end
local function finishTrade(p,receipt)
    local g=E.state(p)
    -- A native mod may perform irreversible work on removal (e.g. change
    -- containers). Do not pretend that adding it back can undo that work.
    if receipt.native and p:GetEffectiveMaxHearts()~=receipt.nativeMax then E.clearUndo(p);return end
    receipt.after=tradeMark(p);g.undo=g.undo or {};g.undo[#g.undo+1]=receipt
end
function E.undo(p,allowed)
    if not allowed then E.clearUndo(p);return false,'战斗中无法交易' end
    if not E.canUndo(p) then return false,'无法撤回' end
    local g=E.state(p);local history=g.undo;local receipt=history[#history]
    if receipt.native then
        local id=receipt.native;local count=p:GetCollectibleNum(id,true)
        g.syncing=true
        -- firstTime=false restores ownership/caches without paying pickup rewards.
        p:AddCollectible(id,0,false)
        g.syncing=false
        if p:GetCollectibleNum(id,true)~=count+1 then E.clearUndo(p);return false,'无法撤回' end
        E.refreshNative(p)
    end
    g.slots=copy(receipt.slots)
    E.addGold(p,receipt.gold-p:GetNumCoins()) -- exact balance, including the 99-coin cap
    Health.restore(p,receipt.health);E.syncHealth(p);Health.sync(p)
    table.remove(history)
    if history[#history] then history[#history].after=tradeMark(p) end
    return true,'已撤回交易'
end
function E.buy(p,id,allowed)
    if not allowed then return false,'战斗中无法交易' end
    E.syncCoins(p)
    local q,err=E.quote(p,id);if not q then return false,err end
    local g=E.state(p);if g.gold<q.cost then return false,'金币不足' end
    local receipt=beforeTrade(p)
    local a=q.slots[q.destination]
    if a.id==id then a.count=a.count+1 else q.slots[q.destination]={id=id,count=1,ready=(g.cooldowns or {})['item'..id] or 0,charges=id==2031 and 2 or 0} end
    g.slots=q.slots;E.addGold(p,-q.cost);E.syncHealth(p);Health.sync(p);finishTrade(p,receipt);return true,'买入成功'
end
function E.sell(p,index,allowed)
    if not allowed then return false,'战斗中无法交易' end
    E.syncCoins(p)
    local g=E.state(p);local a=index and g.slots[index];local item=a and E.items[a.id]
    if not item or item.sell<0 then return false,'不可出售' end
    local receipt=beforeTrade(p)
    local native=a.id<0
    if native then
        local id=-a.id;local before=p:GetCollectibleNum(id,true)
        if before<=0 then E.syncInventory(p);return false,'不可出售' end
        g.syncing=true;p:RemoveCollectible(id,true)
        if p:GetCollectibleNum(id,true)~=before-1 then g.syncing=false;return false,'不可出售' end
        receipt.native=id
    end
    E.addGold(p,item.sell);a.count=a.count-1;if a.count<=0 then g.slots[index]=empty() end
    if native then E.refreshNative(p);g.syncing=false end
    E.syncHealth(p);Health.sync(p);E.coinDisplay(p);finishTrade(p,receipt);return true,'售出成功'
end
function E.stats(p,st)
    local a=E.sum(p);local g=E.state(p);local bonus=a.ad
    if E.has(p,3053) then bonus=bonus+p.Damage*1.8/.105*.45 end
    if E.has(p,2501) then bonus=(bonus+a.hp*.025)*(1+.12*(1-Health.ratio(p))) end
    st.damage=st.damage+bonus*.105
    st.interval=math.max(3,st.interval/(1+a.attackSpeed))
    st.crit=math.min(1,st.crit+a.crit);st.critMultiplier=1.75+a.critDamage
    if (E.has(p,3009) or E.has(p,3170)) and p.HasEntityFlags and p:HasEntityFlags(EntityFlag.FLAG_SLOW) then st.speed=st.speed*1.25 end
    local onHitSpeed=(E.has(p,3044) or E.has(p,3071) or E.has(p,3078) or E.has(p,4629)) and (g.speedUntil or 0)>g.time
    st.speed=math.min(5.5,st.speed*(1+a.movePercent+a.move/345)*(onHitSpeed and 1.3 or 1))
    if E.has(p,3094) and (g.energized or 0)>=100 then st.reach=st.reach*1.35 end
    return st
end
function E.activeSpeed(p)
    local g=E.state(p)
    return E.has(p,3142) and (g.youmuuUntil or 0)>g.time and 1.3 or 1
end
function E.cooldown(p,ticks,ultimate)
    local a=E.sum(p);local haste=a.haste+Balance.hastePerAttackSpeed*30/math.max(.01,p.MaxFireDelay+1)
    if ultimate and (E.has(p,3073) or E.has(p,2512)) then haste=haste+30 end
    if ultimate and E.has(p,3118) then haste=haste+20 end
    if not ultimate and E.has(p,3161) then haste=haste+25 end
    return math.max(1,math.floor(ticks*100/(100+haste)))
end
function E.heal(p,hp)
    local g=E.state(p);local mult=1+E.sum(p).healPower;if E.has(p,3065) then mult=mult*1.25 end;if E.has(p,6617) then mult=mult*1.2 end
    Health.heal(p,math.max(0,hp)*mult)
end
function E.kill(e,isSamira)
    local d=e:GetData();local mark=d.SamiraLastHit
    if d.SamiraGoldClaimed or not mark or not mark.owner or not mark.owner:Exists() or not isSamira(mark.owner) then return false end
    local p=mark.owner;local s=p:GetData().Samira
    if not s or s.clock-mark.clock>90 or e:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) then return false end
    d.SamiraGoldClaimed=true;local g=E.state(p);g.kills=g.kills+1
    if E.has(p,1082) or E.has(p,3041) then g.soulStacks=math.min(E.has(p,3041) and 25 or 10,(g.soulStacks or 0)+(e:IsBoss() and 4 or 1)) end
    if E.has(p,6697) then g.hubris=math.min(35,(g.hubris or 15)+2);g.hubrisUntil=g.time+2700 end
    if E.has(p,2517) then g.hungerUntil=g.time+240;E.heal(p,100) end
    if E.has(p,6696) then s.rReady=math.max(s.clock,s.rReady-720) end
    if E.has(p,6333) and e:IsBoss() then E.heal(p,80);g.debt=0 end
    if E.has(p,3137) and g.time>=(g.bloomReady or 0) then E.heal(p,100+E.sum(p).ap*.2);g.bloomReady=g.time+1800 end
    if E.has(p,2520) then g.sabotage=g.time+300 end
    if E.has(p,3008) or E.has(p,3168) then g.bootKills=math.min(10,(g.bootKills or 0)+1) end
    for _,id in ipairs({1101,1102,1103,1105,1106,1107}) do if E.has(p,id) then g.petKills=math.min(20,(g.petKills or 0)+1);E.heal(p,20);if id==1102 or id==1106 then g.speedUntil=g.time+120 end;break end end
    g.stacks=math.min(25,g.stacks+1);g.dirty=true;return true
end
function E.room(p,clear)
    E.clearUndo(p)
    local g=E.state(p);g.redemption=nil
    if clear then for _,a in ipairs(g.slots) do if a.id==2031 then a.charges=2 end end end
end
return E
