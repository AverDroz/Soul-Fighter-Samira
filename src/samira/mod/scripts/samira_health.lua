-- Authoritative floating-point HP. Native hearts are only a pickup/item bridge.
-- Keep state on the player: Isaac include() does not cache module instances.
local H={VERSION=1,HALF_HEART=50,HURT_HALF_FRAMES=40,HURT_FULL_FRAMES=80} -- 60 Hz: 2/3 s or 4/3 s.
local function finite(n,default)
    return type(n)=='number' and n==n and math.abs(n)<1e9 and n or default
end
local function snapshot(p)
    return {red=p:GetHearts(),soul=p:GetSoulHearts(),max=p:GetEffectiveMaxHearts(),
        broken=p.GetBrokenHearts and p:GetBrokenHearts() or 0}
end
local function growth(p)
    local n=math.max(0,((p:GetData().SamiraProgress or {}).level or 1)-1)
    return 114*(.7025*n+.0175*n*n)
end
local function maximum(h)return math.max(0,650+h.nativeBonus+h.growth+h.gear)end
function H.restore(p,saved,legacy)
    local native=snapshot(p);local oldGear=p:GetData().SamiraGear or {}
    local h={version=H.VERSION,growth=growth(p),gear=0,nativeBonus=0,soul=0,hp=650}
    p:GetData().SamiraHealth=h
    if type(saved)=='table' and saved.version==H.VERSION then
        h.nativeBonus=finite(saved.nativeBonus,0);h.gear=math.max(0,finite(saved.gear,0))
        h.hp=math.max(0,finite(saved.hp,650));h.soul=math.max(0,finite(saved.soul,0))
    else
        local granted=legacy and math.min(math.max(0,native.max-6),math.floor(h.growth*6/650)+(oldGear.grantedHP or 0)) or 0
        h.nativeBonus=(native.max-granted-6)*50-native.broken*100
        -- Old saves already contain their level/equipment heart containers.
        -- Remove only those grants under the bridge guard, once, without healing.
        if granted>0 then h.syncing=true;p:AddMaxHearts(-granted,false);h.syncing=nil end
        h.hp=maximum(h)*math.min(1,native.red/math.max(1,native.max))
        h.soul=native.soul*50
        if legacy then
            h.legacyRatio=math.min(1,native.red/math.max(1,native.max))
            oldGear.debt=(oldGear.debt or 0)*50
            local progress=p:GetData().SamiraProgress or {}
            h.legacyCredit=((oldGear.heal or 0)+(progress.passiveHeal or 0))*650/6
            h.legacyDamage=(oldGear.damageBank or 0)*50
            oldGear.heal=0;oldGear.damageBank=0;progress.passiveHeal=0
        end
    end
    h.hp=math.min(h.hp,maximum(h));h.native=snapshot(p)
    return h
end
function H.state(p)return p:GetData().SamiraHealth or H.restore(p)end
function H.max(p)return maximum(H.state(p))end
function H.current(p)return H.state(p).hp end
function H.missing(p)return H.max(p)-H.current(p)end
function H.ratio(p)return H.current(p)/math.max(1,H.max(p))end
function H.floorMultiplier(stage)
    return 1+.2*(math.max(1,stage or Game():GetLevel():GetAbsoluteStage())-1)
end
function H.setGear(p,hp)
    local h=H.state(p);h.gear=math.max(0,hp)
    if h.legacyRatio then
        h.hp=math.min(maximum(h),maximum(h)*h.legacyRatio+(h.legacyCredit or 0))
        local owed=h.legacyDamage or 0;local absorbed=math.min(h.soul,owed)
        h.soul=h.soul-absorbed;h.hp=math.max(0,h.hp-owed+absorbed)
        h.legacyRatio=nil;h.legacyCredit=nil;h.legacyDamage=nil
    end
    h.hp=math.min(h.hp,maximum(h))
end
function H.levelUp(p)
    local h=H.state(p);local delta=growth(p)-h.growth
    h.growth=growth(p);h.hp=math.min(maximum(h),math.max(0,h.hp+delta))
end
function H.heal(p,amount)
    local h=H.state(p);if p:IsDead() or h.hp+h.soul<=0 then return 0 end
    local before=h.hp;h.hp=math.min(maximum(h),h.hp+math.max(0,amount));return h.hp-before
end
local function death(p,h)
    if h.hp+h.soul<=0 and not p:IsDead() and not h.killing then
        h.killing=true;p:Kill();h.killing=nil
    end
end
function H.damage(p,amount,redOnly)
    local h=H.state(p);amount=math.max(0,amount)
    if not redOnly then local absorbed=math.min(h.soul,amount);h.soul=h.soul-absorbed;amount=amount-absorbed end
    h.hp=math.max(0,h.hp-amount);death(p,h)
end
function H.queue(p,amount,redOnly,flags,equipment,nativeDamage)
    -- Use the native half-heart units before floor scaling, armor or shields.
    local hurtFrames=(nativeDamage or 1)>=2 and H.HURT_FULL_FRAMES or H.HURT_HALF_FRAMES
    H.state(p).pending={amount=amount,redOnly=redOnly,equipment=equipment,hurtFrames=hurtFrames,
        shortHurt=(flags & (DamageFlag.DAMAGE_NO_PENALTIES|DamageFlag.DAMAGE_RED_HEARTS|DamageFlag.DAMAGE_INVINCIBLE))==0}
    -- REPENTOGON explicitly supports adding DAMAGE_FAKE here: native hurt
    -- animation, invulnerability and callbacks run without spending proxy hearts.
    return {DamageFlags=flags|DamageFlag.DAMAGE_FAKE}
end
function H.commit(p)
    local h=H.state(p);local pending=h.pending;h.pending=nil
    if pending then
        local gear=p:GetData().SamiraGear;local effects=pending.equipment
        local state=p:GetData().Samira
        if state and (pending.amount>0 or effects and effects.shield>0) then state.screenHitAt=state.clock end
        if gear and effects then
            if effects.debt>0 then gear.debt=(gear.debt or 0)+effects.debt;gear.debtUntil=gear.time+90 end
            gear.shield=math.max(0,(gear.shield or 0)-effects.shield)
        end
        H.damage(p,pending.amount,pending.redOnly)
        -- Only shorten an accepted ordinary hit, never continuously clamp item invulnerability.
        if pending.shortHurt and not p:IsDead() and p:GetDamageCooldown()>pending.hurtFrames then
            p:ResetDamageCooldown();p:SetMinDamageCooldown(pending.hurtFrames)
        end
    end
end
-- AddBlackHearts/eternal conversions can call other Add* functions internally.
-- Aggregate one outer transaction to avoid paying for the same heart twice.
function H.preAdd(p,amount,kind)
    local h=p:GetData().SamiraHealth;if not h or h.syncing then return end
    if not h.transaction then h.transaction={before=snapshot(p),red=0,depth=0,kind=kind} end
    local t=h.transaction;t.depth=t.depth+1
end
local function reconcile(p,h,before,after,red)
    local brokenDelta=after.broken-before.broken
    local capDelta=brokenDelta~=0 and -brokenDelta*100 or (after.max-before.max)*50
    h.nativeBonus=h.nativeBonus+capDelta
    h.hp=math.min(maximum(h),math.max(0,h.hp+red*50))
    h.soul=math.max(0,h.soul+(after.soul-before.soul)*50)
    h.native=after
end
function H.postAdd(p,amount,kind)
    local h=p:GetData().SamiraHealth;if not h or h.syncing or not h.transaction then return end
    local t=h.transaction
    if kind==1 then t.red=t.red+amount;t.sawRed=true end
    t.depth=t.depth-1;if t.depth>0 then return end
    h.transaction=nil
    local after=snapshot(p)
    -- Capacity removal may clamp native red hearts; this is not extra damage.
    local red=t.sawRed and t.red or (kind==128 and after.red-t.before.red or 0)
    if t.kind==2 and red<0 then red=0 end
    reconcile(p,h,t.before,after,red)
    death(p,h);H.sync(p)
end
function H.sync(p)
    local h=H.state(p);if p:IsDead() then return end
    h.syncing=true
    local cap=p:GetEffectiveMaxHearts()
    -- The native pool is not the health authority. Retain one proxy container
    -- when native costs remove the last one but numeric HP is still positive.
    if cap<2 and h.hp>0 then
        p:AddMaxHearts(2-cap,false);cap=p:GetEffectiveMaxHearts()
    end
    local red=math.floor(h.hp/math.max(1,maximum(h))*cap+1e-7)
    if h.hp>0 then red=math.max(1,red) end
    if h.hp<maximum(h) then red=math.min(math.max(0,cap-1),red) end
    local delta=red-p:GetHearts();if delta~=0 then p:AddHearts(delta) end
    local soul=math.ceil(h.soul/50-1e-9);delta=soul-p:GetSoulHearts()
    if delta~=0 then p:AddSoulHearts(delta) end
    h.syncing=nil;h.native=snapshot(p)
end
function H.update(p)
    local h=H.state(p);h.pending=nil -- another mod may cancel after our callback
    if p:IsDead() then return end
    local now=snapshot(p);local before=h.native
    if before then
        local red=now.red-before.red
        if now.max<before.max and red<0 then red=0 end
        reconcile(p,h,before,now,red)
    end
    death(p,h);H.sync(p)
end
function H.revive(p)
    local h=H.state(p);h.pending=nil;h.killing=nil
    h.hp=math.min(maximum(h),math.max(50,p:GetHearts()*50))
    h.soul=p:GetSoulHearts()*50;h.native=snapshot(p);H.sync(p)
end
function H.save(p)
    local h=H.state(p)
    return {version=H.VERSION,hp=h.hp,soul=h.soul,nativeBonus=h.nativeBonus,gear=h.gear}
end
return H
