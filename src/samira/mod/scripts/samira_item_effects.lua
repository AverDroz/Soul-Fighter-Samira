local Health=include('scripts.samira_health')
local Balance=include('scripts.samira_balance')
-- Isaac equivalents of item combat triggers. Damage uses the existing conversion.
local E=include('scripts.samira_equipment');local G=include('scripts.samira_geometry');local Terrain=include('scripts.samira_terrain')
local F={};local SCALE=.105
local Stasis=include('scripts.samira_stasis')
local ghostbladeSound,zhonyaSound
-- Native dust is cosmetic: no creep damage, costume or Companion dependency.
local function ghostbladeDust(p,offset,scale,life)
    local dust=Isaac.Spawn(EntityType.ENTITY_EFFECT,EffectVariant.DUST_CLOUD,0,
        p.Position+offset,Vector.Zero,p):ToEffect()
    if not dust then return end
    dust.Color=Color(.65,.35,1,.55)
    dust.SpriteScale=Vector(scale,scale)
    dust.DepthOffset=-10
    dust.CollisionDamage=0
    dust.EntityCollisionClass=EntityCollisionClass.ENTCOLL_NONE
    dust.Timeout=life;dust.LifeSpan=life
end
local function alive(e)return e and e:Exists() and not e:IsDead() end
local function hostile(e)return alive(e) and e:IsVulnerableEnemy() and not e:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) end
local function targetKey(e)
    local level=Game():GetLevel()
    return tostring(level:GetAbsoluteStage())..':'..tostring(level:GetCurrentRoomIndex())..':'..tostring(e.InitSeed or e)
end
local function has(p,ids)for _,id in ipairs(ids) do if E.has(p,id) then return id end end end
local function ready(g,key,seconds)
    g.cooldowns=g.cooldowns or {};if g.time<(g.cooldowns[key] or 0) then return false end
    g.cooldowns[key]=g.time+seconds*30;return true
end
local function damage(p,s,e,value,physical)
    if not hostile(e) or value<=0 then return 0 end
    local a=E.sum(p);local percent=physical and a.armorPen or a.magicPenPercent;local flat=physical and a.lethality or a.magicPen
    value=value*1.3/(1+math.max(0,30*(1-percent)-flat)/100)
    e:GetData().SamiraLastHit={owner=p,clock=s.clock}
    local actual=math.min(value,math.max(0,e.HitPoints))
    return e:TakeDamage(value,0,EntityRef(p),0)~=false and actual or 0
end
local function area(p,s,position,radius,value,slow,exclude)
    for _,e in ipairs(Isaac.GetRoomEntities()) do if e~=exclude and hostile(e) and e.Position:Distance(position)<=radius+e.Size then
        damage(p,s,e,value);if slow then e:AddSlowing(EntityRef(p),60,slow,Color(.5,.7,1,1)) end
    end end
end
function F.cast(p,s,key)
    E.clearUndo(p)
    local g=E.state(p);g.spellblade=g.time+300
    if has(p,{3070,3003,3004,3119}) and ready(g,'tear',3) then
        g.tear=math.min(360,(g.tear or 0)+6);g.dirty=true
        if g.tear>=360 then for _,slot in ipairs(g.slots) do local upgraded=({[3003]=3040,[3004]=3042,[3119]=3121})[slot.id];if upgraded then slot.id=upgraded;E.syncHealth(p) end end end
    end
    if E.has(p,3803) or E.has(p,6657) then E.heal(p,5) end
    if key=='r' then
        if E.has(p,3073) or E.has(p,2512) then g.overdrive=g.time+240 end
        if E.has(p,3050) then g.storm=g.time+150 end
    end
end
function F.multiplier(p,s,e,spell,damageType)
    local g=E.state(p);local a=E.sum(p);local multiplier=1
    if spell and E.has(p,3161) then multiplier=multiplier*(1+math.min(4,g.shojin or 0)*.03) end
    if has(p,{3147,6653,4633}) then multiplier=multiplier*(1+math.min(E.has(p,4633) and .08 or .06,(g.combatTicks or 0)/30*.02)) end
    local d=e:GetData();if d.SamiraCarve and d.SamiraCarve.untilTick>s.clock then multiplier=multiplier*(1+.06*d.SamiraCarve.stacks) end
    -- Isaac enemies have no LoL armor: penetration is adapted to a nominal 30 armor layer.
    local magic=damageType=='magic'
    local percent=magic and a.magicPenPercent or a.armorPen
    local flat=magic and a.magicPen or a.lethality
    if damageType~='true' then multiplier=multiplier*1.3/(1+math.max(0,30*(1-percent)-flat)/100) end
    if spell and E.has(p,4628) and e.Position:Distance(p.Position)>=110 then multiplier=multiplier*1.1 end
    if spell and E.has(p,4645) and e.HitPoints<e.MaxHitPoints*.4 then multiplier=multiplier*1.2 end
    if spell and (g.empower or 0)>g.time then multiplier=multiplier*1.2 end
    if spell and E.has(p,8020) and e.Position:Distance(p.Position)<110 then multiplier=multiplier*1.12 end
    if E.has(p,3168) and Health.ratio(p)>.5 then multiplier=multiplier*1.04 end
    if E.has(p,3036) then multiplier=multiplier*(1+math.min(.15,(e.MaxHitPoints or 0)/10000)) end
    if E.has(p,2523) and not spell then multiplier=multiplier*(1+.1*math.min(1,e.Position:Distance(p.Position)/140)) end
    return multiplier
end
function F.hit(p,s,e,amount,spell,healAmount,healthBefore)
    if amount<=0 then return end -- Only accepted, positive damage can trigger equipment.
    E.clearUndo(p)
    local g=E.state(p);local a=E.sum(p);local first=g.lastImpact~=g.time;g.lastImpact=g.time;g.combatUntil=g.time+180
    if first then g.energized=math.min(100,(g.energized or 0)+6) end
    if has(p,{3123,3916,3033,3165,6609,3075}) then e:GetData().SamiraWounds={untilTick=s.clock+90,hp=e.HitPoints} end
    if spell and has(p,{2526,2530}) and ready(g,'circlet',8) then
        g.circlet=math.min(360,(g.circlet or 0)+8);g.dirty=true
        if g.circlet>=360 then for _,slot in ipairs(g.slots) do if slot.id==2526 and E.items[2530] then slot.id=2530 end end end
    end
    if first and spell and E.has(p,2520) and ready(g,'bastion',10) then damage(p,s,e,50*SCALE) end
    if first and has(p,{1101,1107}) and (g.petKills or 0)>=20 and ready(g,'petBurn',8) then e:GetData().SamiraBurn={owner=p,untilTick=s.clock+90,nextTick=s.clock+30,damage=15*SCALE};e:AddSlowing(EntityRef(p),60,.7,Color(.8,.3,.2,1)) end
    if spell and has(p,{3171,2524}) then g.speedUntil=g.time+120;g.pipesUntil=g.time+120 end
    if spell and E.has(p,4629) then g.speedUntil=g.time+120 end
    if has(p,{3044,3078}) then g.speedUntil=g.time+60 end
    if spell and E.has(p,8010) then local d=e:GetData();d.SamiraCarve={stacks=math.min(5,((d.SamiraCarve or {}).stacks or 0)+1),untilTick=s.clock+180} end
    if first and E.has(p,4005) and spell and ready(g,'mandate',9) then damage(p,s,e,50*SCALE);g.speedUntil=g.time+60 end
    if first and has(p,{3504,6616,6617,6620,3870}) and ready(g,'supportHeal',3) then E.heal(p,15);g.supportBuff=g.time+180;if E.has(p,6620) then damage(p,s,e,20*SCALE) end end
    if first and has(p,{3865,3866,3867}) and ready(g,'supportGold',8) then g.supportGold=(g.supportGold or 0)+20;g.dirty=true;for _,slot in ipairs(g.slots) do if slot.id==3865 and g.supportGold>=500 then slot.id=3866 elseif slot.id==3866 and g.supportGold>=1000 then slot.id=3869;E.syncHealth(p) end end end
    E.heal(p,math.min(amount,math.max(0,healAmount or amount))/SCALE*(a.omnivamp+(spell and 0 or a.lifesteal)))
    if E.has(p,3071) then local old=e:GetData().SamiraCarve;e:GetData().SamiraCarve={stacks=math.min(5,(old and old.untilTick>s.clock and old.stacks or 0)+1),untilTick=s.clock+180};g.speedUntil=g.time+60 end
    if spell and first and E.has(p,3161) then g.shojin=math.min(4,(g.shojin or 0)+1);g.shojinUntil=g.time+180 end
    if not spell then
        if first then g.attacks=(g.attacks or 0)+1;if E.has(p,3032) then g.yuntal=math.min(125,(g.yuntal or 0)+1) end end
        local bonus=0;local magicBonus=0
        if E.has(p,1120) then bonus=bonus+5 end
        if E.has(p,1043) then bonus=bonus+5 end
        if E.has(p,3115) then magicBonus=magicBonus+15+a.ap*.15 end
        if E.has(p,3091) then bonus=bonus+45 end
        if E.has(p,3124) then bonus=bonus+30;if first then g.rage=math.min(4,(g.rage or 0)+1);g.rageUntil=g.time+120 end end
        if E.has(p,3302) then bonus=bonus+30;g.terminus=math.min(6,(g.terminus or 0)+1);g.terminusUntil=g.time+150 end
        if E.has(p,3042) then bonus=bonus+a.mana*.015 end
        if E.has(p,3742) and (g.energized or 0)>=100 then bonus=bonus+100;g.energized=0;e:AddSlowing(EntityRef(p),30,.5,Color(.5,.7,1,1)) end
        if E.has(p,6670) then bonus=bonus+15 end
        if first and E.has(p,3153) then
            local edge=math.min(100,math.max(0,healthBefore or e.HitPoints)/SCALE*.08)
            -- Life steal is based on accepted damage, not boss maximum HP/overkill.
            local actual=damage(p,s,e,edge*SCALE,true)
            E.heal(p,actual/SCALE*a.lifesteal)
            local d=e:GetData();local key='bork:'..targetKey(e)
            local mark=d.SamiraBork
            if not mark or mark.untilTick<g.time or mark.owner~=p then mark={hits=0,owner=p};d.SamiraBork=mark end
            mark.hits=mark.hits+1;mark.untilTick=g.time+180
            if mark.hits>=3 and ready(g,key,15) then mark.hits=0;e:AddSlowing(EntityRef(p),30,.7,Color.Default) end
        end
        if E.has(p,6672) and (g.attacks or 0)%3==0 then bonus=bonus+100 end
        if E.has(p,3181) and (g.attacks or 0)%5==0 then bonus=bonus+100+a.hp*.05 end
        if E.has(p,1083) then E.heal(p,3) end
        if first and g.spellblade and g.spellblade>=g.time and has(p,{3057,3078,3100,3508,6662,2510,3877}) and ready(g,'spellblade',1.5) then
            local proc=p.Damage*1.8/SCALE*(E.has(p,3078) and 2 or 1)+(E.has(p,3100) and a.ap*.45 or 0)
            if E.has(p,3100) then magicBonus=magicBonus+proc else bonus=bonus+proc end;g.spellblade=nil
            if E.has(p,6662) then area(p,s,e.Position,60,0,.5) end
        end
        local targetData=e:GetData()
        if first and E.has(p,6610) and (targetData.SamiraSunderUntil or 0)<=s.clock then
            targetData.SamiraSunderUntil=s.clock+240
            bonus=bonus+amount/SCALE*.75;E.heal(p,35+Health.missing(p)*.03)
        end
        if first and E.has(p,3084) then
            local mark=(g.heartsteelTargets or {})[targetKey(e)]
            if mark and mark.charge>=90 and g.time>=mark.ready and g.time-mark.seen<=90 then
                local impact=70+Health.max(p)*.06
                bonus=bonus+impact;mark.charge=0;mark.ready=g.time+900
                local gain=impact*.1;g.heartsteel=(g.heartsteel or 0)+gain
                E.syncHealth(p);Health.heal(p,gain);g.dirty=true
                s.heartsteelHits=s.heartsteelHits or {}
                s.heartsteelHits[#s.heartsteelHits+1]={position=e.Position,at=s.clock,size=e.Size}
                if #s.heartsteelHits>12 then table.remove(s.heartsteelHits,1) end
                s.heartsteelSoundPending=true
            end
        end
        if first and has(p,{3094,3095,3087,6699}) and (g.energized or 0)>=100 then
            bonus=bonus+40;g.energized=0
            if E.has(p,3087) then area(p,s,e.Position,110,40*SCALE) end
            if E.has(p,3095) then g.speedUntil=g.time+45 end
        end
        if first and has(p,{3077,3074,3748,6631,6698}) and ready(g,'cleave',.3) then area(p,s,e.Position,55,amount*.35,nil,e) end
        if first and E.has(p,3085) then
            local n=0;for _,target in ipairs(Isaac.GetRoomEntities()) do if target~=e and hostile(target) and target.Position:Distance(e.Position)<140 then damage(p,s,target,amount*.4);n=n+1;if n==2 then break end end end
        end
        if first and E.has(p,6675) then for _,key in ipairs({'qReady','wReady','eReady'}) do s[key]=s.clock+math.max(0,s[key]-s.clock)*.85 end end
        if E.has(p,3124) and (g.rage or 0)>=4 and (g.attacks or 0)%3==0 then bonus=bonus*2 end
        if (g.sabotage or 0)>g.time and e:IsBoss() then bonus=bonus+150;g.sabotage=nil end
        if bonus>0 then damage(p,s,e,bonus*SCALE,true) end
        if magicBonus>0 then damage(p,s,e,magicBonus*SCALE,false) end
    end
    if has(p,{3116,6694}) and spell then
        e:AddSlowing(EntityRef(p),30,.7,Color(.5,.7,1,1))
        local countdown=e.GetSlowingCountdown and e:GetSlowingCountdown()
        if countdown==nil or countdown>0 then e:GetData().SamiraEquipmentSlow={untilTick=s.clock+30,owner=p} end
        -- Record the engine's response, not just that Lua called AddSlowing.
        if E.has(p,6694) and g.time>=(g.slowDiagnosticAt or 0) then
            g.slowDiagnosticAt=g.time+90
            Isaac.DebugString('[Samira equipment] Serylda spell hit; npc='..tostring(e.Type)..':'..tostring(e.Variant)..'; dead='..tostring(e:IsDead())..'; native slow ticks='..tostring(countdown))
        end
    end
    if spell and (has(p,{2508,2503,6653}) or E.has(p,3118) and (s.rUntil or 0)>s.clock) then
        e:GetData().SamiraBurn={owner=p,untilTick=s.clock+90,nextTick=s.clock+30,damage=E.has(p,6653) and math.max(1,(e.MaxHitPoints or e.HitPoints)*.02) or (5+a.ap*.02)*SCALE}
    end
    if spell and first and has(p,{3144,3145,6655,4646,3871}) and ready(g,'burst',10) then area(p,s,e.Position,85,((E.has(p,6655) and 60 or 40)+a.ap*.1)*SCALE) end
    if E.has(p,6676) and e.HitPoints>0 and e.MaxHitPoints and e.HitPoints/e.MaxHitPoints<.05 then damage(p,s,e,e.HitPoints+1) end
    if first and E.has(p,3121) and spell and ready(g,'winter',8) then g.shield=100+a.mana*.05;g.shieldUntil=g.time+90 end
    if first and E.has(p,3876) and spell and ready(g,'sleigh',20) then E.heal(p,80);g.speedUntil=g.time+90 end
    if first and E.has(p,6692) then
        if g.eclipseHit and g.time-g.eclipseHit<60 and ready(g,'eclipse',6) then g.shield=120+a.ad*.4;g.shieldUntil=g.time+60 end;g.eclipseHit=g.time
    end
end
local actives={ [2003]='potion',[2031]='refill',[2138]='iron',[2139]='sorcery',[2140]='wrath',[2141]='juice',
 [2420]='stasis',[3157]='stasis',[3077]='cleave',[3074]='cleave',[3748]='cleave',[6698]='cleave',[6631]='cleave',
 [3140]='cleanse',[3139]='cleanse',[3222]='cleanse',[3142]='speed',[2065]='speed',[3190]='shield',[3107]='redemption',
 [3146]='bolt',[3152]='rocket',[3143]='slow',[2522]='empower',[3109]='pledge',
 [2055]='vision',[3340]='vision',[3363]='vision',[3364]='vision',[3869]='vision',[3870]='vision',[3871]='vision',[3876]='vision',[3877]='vision'}
function F.active(id)return actives[id] end
F.stasis=Stasis
function F.use(p,s,index,aim)
    E.clearUndo(p)
    local g=E.state(p);local slot=g.slots[index];local kind=slot and actives[slot.id]
    if not kind or (kind~='stasis' and (s.cast or s.dash)) or (g.stasis or 0)>g.time or g.time<(slot.ready or 0) or p:IsDead() then return false end
    local id=slot.id;local a=E.sum(p);local duration=kind=='stasis' and 120 or kind=='cleave' and 10 or kind=='vision' and 60 or 60
    if kind=='refill' and slot.charges<=0 then return false end
    if (kind=='refill' or kind=='potion') and ((g.potionUntil or 0)>g.time or Health.ratio(p)>=1) then return false end
    if not ready(g,'item'..id,(kind=='refill' or kind=='potion') and 1 or duration) then return false end
    if kind=='potion' or kind=='refill' then
        g.potionUntil=g.time+(kind=='potion' and 450 or 360);g.potionRate=kind=='potion' and 8 or 100/12
        if kind=='refill' then slot.charges=slot.charges-1 end
    elseif kind=='stasis' then
        -- Cancel the actor's pending attack/channel/dash, never an existing aura or projectile.
        if s.dash then Terrain.finish(Game():GetRoom(),p,s,true) end
        g.stasis=g.time+75;s.goal=nil;s.target=nil;s.gridTarget=nil;s.cast=nil;s.emote=nil;s.weaponMotion=nil
        Stasis.update(p,g)
        zhonyaSound=zhonyaSound or Isaac.GetSoundIdByName('Samira zhonya_activate')
        if zhonyaSound>0 then SFXManager():Play(zhonyaSound,.8,0,false,1) end
    elseif kind=='cleave' then area(p,s,p.Position,115,(p.Damage*1.8+a.ad*SCALE)*(id==6698 and 1.1 or .8),id==6631 and .65 or nil);if id==6631 then g.speedUntil=g.time+90 end
    elseif kind=='speed' then
        if id==3142 then
            g.youmuuUntil=g.time+120
            ghostbladeSound=ghostbladeSound or Isaac.GetSoundIdByName('Samira youmuu_activate')
            if ghostbladeSound>0 then SFXManager():Play(ghostbladeSound,.8,0,false,1) end
            ghostbladeDust(p,Vector(-14,0),.65,12)
            ghostbladeDust(p,Vector(14,0),.65,12)
        else g.speedUntil=g.time+120 end
    elseif kind=='shield' then g.shield=300;g.shieldUntil=g.time+75
    elseif kind=='cleanse' then p:ClearEntityFlags(EntityFlag.FLAG_SLOW|EntityFlag.FLAG_CONFUSION|EntityFlag.FLAG_FEAR);g.speedUntil=g.time+45;if id==3222 then E.heal(p,150) end
    elseif kind=='redemption' then g.redemption={x=aim.X,y=aim.Y,at=g.time+75}
    elseif kind=='bolt' then area(p,s,aim,55,(100+a.ap*.3)*SCALE,.75)
    elseif kind=='rocket' then local d=G.unproject(aim-p.Position);if d:Length()>1 then Terrain.begin(Game():GetRoom(),p,s,d:Normalized(),77) end;area(p,s,aim,90,(100+a.ap*.1)*SCALE)
    elseif kind=='slow' then area(p,s,p.Position,140,0,.3)
    elseif kind=='vision' then Game():GetLevel():RevealMap()
    elseif kind=='iron' then g.ironUntil=g.time+5400;E.syncHealth(p)
    elseif kind=='wrath' or kind=='sorcery' then g.elixir=kind;g.elixirUntil=g.time+5400
    elseif kind=='empower' then g.empower=g.time+240
    elseif kind=='pledge' then g.vowUntil=g.time+300
    elseif kind=='juice' then g.hat=true end
    slot.ready=g.time+((kind=='potion' or kind=='refill') and 30 or duration*30)
    g.dirty=true
    if E.items[id].consumed or id==2003 or id==2055 or id>=2138 and id<=2141 then slot.count=slot.count-1;if slot.count<=0 then g.slots[index]={id=0,count=0,ready=0,charges=0} end end
    if id==2420 then slot.id=2421 end
    return true
end
function F.update(p,s)
    local g=E.state(p);g.time=g.time+1;local a=E.sum(p)
    if (g.youmuuUntil or 0)>g.time and E.has(p,3142) and not p:IsDead()
        and p.Velocity:Length()>.2 and g.time%4==0 then
        ghostbladeDust(p,p.Velocity:Normalized()*-12,.45,math.min(10,g.youmuuUntil-g.time))
    end
    local steel=E.has(p,3084);s.heartsteelVisuals={}
    for i=#(s.heartsteelHits or {}),1,-1 do
        local age=s.clock-s.heartsteelHits[i].at
        if age<0 or age>=90 then table.remove(s.heartsteelHits,i) end
    end
    g.heartsteelTargets=g.heartsteelTargets or {}
    if g.time%90==0 then
        for key,v in pairs(g.heartsteelTargets) do if g.time-v.seen>90 and g.time>=v.ready then g.heartsteelTargets[key]=nil end end
        for key,v in pairs(g.cooldowns or {}) do if key:sub(1,5)=='bork:' and v<=g.time then g.cooldowns[key]=nil end end
    end
    if p.Velocity:Length()>.2 then g.energized=math.min(100,(g.energized or 0)+.3) end
    if (g.combatUntil or 0)>g.time then g.combatTicks=(g.combatTicks or 0)+1 else g.combatTicks=0;g.shojin=0 end
    if g.time>=(g.shojinUntil or 0) then g.shojin=0 end
    if g.shieldUntil and g.time>=g.shieldUntil then g.shield=0 end
    if E.has(p,6657) then g.rodTime=(g.rodTime or 0)+1;if g.rodTime%1800==0 then E.syncHealth(p);g.dirty=true end end
    if g.ironUntil and g.time==g.ironUntil then E.syncHealth(p);g.dirty=true end
    if g.debtUntil and g.time<=g.debtUntil and g.time%15==0 and (g.debt or 0)>0 then
        local part=g.debt/math.max(1,math.ceil((g.debtUntil-g.time+1)/15));g.debt=g.debt-part
        if not Stasis.active(p,g) then Health.damage(p,part) end
    end
    if g.rebirth and g.time>=g.rebirth then Health.heal(p,math.max(0,Health.max(p)*.5-Health.current(p)));g.rebirth=nil end
    Stasis.update(p,g)
    if g.redemption and g.time>=g.redemption.at then local center=Vector(g.redemption.x,g.redemption.y);area(p,s,center,155,20*SCALE);if p.Position:Distance(center)<=155 then E.heal(p,200) end;g.redemption=nil end
    if g.time%30==0 then
        if has(p,{1101,1102,1103,1105,1106,1107}) then
            local target,best=nil,150;for _,e in ipairs(Isaac.GetRoomEntities()) do if hostile(e) and e.Position:Distance(p.Position)<best then target=e;best=e.Position:Distance(p.Position) end end
            if target then damage(p,s,target,(15+a.ad*.1+a.ap*.1)*SCALE) end
            if (g.petKills or 0)>=20 and has(p,{1103,1105}) and g.time>(g.lastHurt or 0)+300 then g.shield=math.max(g.shield or 0,150);g.shieldUntil=g.time+120 end
        end
        if a.regenPercent>0 or a.regen>0 then E.heal(p,1.4*a.regenPercent+a.regen/5) end
        if E.has(p,1054) and g.time<(g.lastHurt or -999)+240 then E.heal(p,2) end
        if E.has(p,2051) or E.has(p,3112) then E.heal(p,4) end
        if E.has(p,2504) and g.time>(g.lastHurt or 0)+450 and ready(g,'kaenic',15) then g.shield=Health.max(p)*.15;g.shieldUntil=g.time+900 end
        if E.has(p,3072) and Health.ratio(p)>=1 then g.shield=math.max(g.shield or 0,150);g.shieldUntil=g.time+120 end
        if E.has(p,3179) and ready(g,'umbral',45) then Game():GetLevel():RevealMap() end
        if E.has(p,1056) then E.heal(p,.45) end
        if g.potionUntil and g.time<g.potionUntil then E.heal(p,g.potionRate) end
        if E.has(p,3083) and a.hp>=2000 and g.time>(g.lastHurt or 0)+240 then E.heal(p,Health.max(p)*.05) end
        if has(p,{6660,3068,6664,2502}) and (g.combatUntil or 0)>g.time then area(p,s,p.Position,90,(12+a.hp*.01)*SCALE);if E.has(p,2502) and g.time%120==0 then E.heal(p,40) end end
        if g.storm and g.time<g.storm then area(p,s,p.Position,100,30*SCALE,.7) end
    end
    for _,e in ipairs(Isaac.GetRoomEntities()) do if hostile(e) then
        if steel and e.Type~=EntityType.ENTITY_FIREPLACE then
            local key=targetKey(e);local mark=g.heartsteelTargets[key]
            if e.Position:Distance(p.Position)<=700*G.units+e.Size then
                mark=mark or {charge=0,seen=g.time,ready=0};g.heartsteelTargets[key]=mark
                if g.time-mark.seen>90 then mark.charge=0 end
                mark.seen=g.time
                if g.time>=mark.ready then
                    local previous=math.max(1,math.floor(mark.charge/15))
                    mark.charge=math.min(90,mark.charge+1)
                    if mark.charge==1 or previous~=math.max(1,math.floor(mark.charge/15)) then mark.stageAt=g.time end
                end
            end
            if mark and g.time>=mark.ready and g.time-mark.seen<=90 and mark.charge>0 then
                s.heartsteelVisuals[#s.heartsteelVisuals+1]={target=e,charge=mark.charge,key=key,age=g.time-(mark.stageAt or g.time)}
            end
        end
        if E.has(p,3110) and e.Position:Distance(p.Position)<130 then e:AddSlowing(EntityRef(p),2,.85,Color(.5,.7,1,1)) end
        local wound=e:GetData().SamiraWounds
        if wound and s.clock<wound.untilTick then if e.HitPoints>wound.hp then e.HitPoints=wound.hp+(e.HitPoints-wound.hp)*.6 end;wound.hp=e.HitPoints end
        local burn=e:GetData().SamiraBurn
        if burn and burn.owner==p then
            if s.clock>=burn.untilTick then e:GetData().SamiraBurn=nil
            elseif s.clock>=burn.nextTick then damage(p,s,e,burn.damage);burn.nextTick=s.clock+30 end
        end
    end end
end
function F.hurt(p,s,amount,flags,source,countdown)
    Health.state(p).pending=nil
    local g=E.state(p);if g.damageGuard then return end
    if amount<=0 then return end
    if (g.stasis or 0)>g.time then return false end
    if (flags & DamageFlag.DAMAGE_FAKE)~=0 then return end
    E.clearUndo(p)
    local cost=(flags & (DamageFlag.DAMAGE_NO_PENALTIES|DamageFlag.DAMAGE_RED_HEARTS))~=0
    if cost then return Health.queue(p,amount*50*Health.floorMultiplier(),(flags & DamageFlag.DAMAGE_RED_HEARTS)~=0,flags) end
    local a=E.sum(p);local magic=source and source.Entity and source.Entity.Type==EntityType.ENTITY_PROJECTILE
    local delayed,shieldSpent=0,0
    local defense=magic and a.mr or a.armor;local damageUnits=amount*50*Health.floorMultiplier()*Balance.incomingDamageMultiplier*100/(100+defense)
    if magic and E.has(p,3173) and ready(g,'chainlaced',20) then g.shield=150;g.shieldUntil=g.time+150 end
    if magic and E.has(p,4401) then g.forceStacks=math.min(8,(g.forceStacks or 0)+1);g.forceUntil=g.time+210 end
    if not magic and has(p,{3047,3174}) then damageUnits=damageUnits*.9 end
    if not magic and has(p,{3082,3110,3143,2051}) then damageUnits=damageUnits*.9 end
    if (g.vowUntil or 0)>g.time then damageUnits=damageUnits*.9 end
    if E.has(p,6333) then delayed=damageUnits*.3;damageUnits=damageUnits-delayed end
    g.lastHurt=g.time;g.combatUntil=g.time+180
    if magic and has(p,{3102,4632,3814}) and ready(g,'spellshield',40) then return false end
    if E.has(p,3869) and ready(g,'celestial',20) then damageUnits=damageUnits*.6 end
    if Health.current(p)+Health.state(p).soul-damageUnits<=0 and E.has(p,3026) and ready(g,'revive',300) then g.stasis=g.time+120;g.rebirth=g.time+120;return false end
    if (Health.current(p)+Health.state(p).soul-damageUnits)/math.max(1,Health.max(p)+Health.state(p).soul)<.3 and has(p,{3053,3155,3156,6673,2525,3040}) and ready(g,'lifeline',90) then g.shield=250+a.hp*.25;g.shieldUntil=g.time+120 end
    if (g.shield or 0)>0 then local factor=(1+a.healPower)*(E.has(p,3065) and 1.25 or 1);local absorb=math.min(g.shield*factor,damageUnits);shieldSpent=absorb/factor;damageUnits=damageUnits-absorb end
    if has(p,{3075,3076}) and source and hostile(source.Entity) then damage(p,s,source.Entity,(10+a.armor*.1)*SCALE) end
    return Health.queue(p,damageUnits,false,flags,{debt=delayed,shield=shieldSpent},amount)
end
return F
