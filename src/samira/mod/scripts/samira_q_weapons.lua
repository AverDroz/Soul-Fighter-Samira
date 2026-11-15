-- Native weapon factories preserve Isaac's item visuals and projectile behavior.
-- Called once at Q contact, never once per victim or from a damage callback.
local W={}
-- Charge adapters run once per completed Q3, independently of blades/victims.
-- Lil Brimstone has no exposed Weapon; FireProjectile would fire a normal tear.
function W.charged(p,s,cast,face)
    if cast.chargeReleased then return end
    cast.chargeReleased=true
    for _,entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type==EntityType.ENTITY_FAMILIAR and entity.Variant==FamiliarVariant.LIL_BRIMSTONE then
            local f=entity:ToFamiliar()
            if f and f.Player and GetPtrHash(f.Player)==GetPtrHash(p) and f:Exists() and not f:IsDead() then
                local laser=p:FireBrimstone(face,f,.5)
                if laser then
                    laser.Position=Vector(f.Position.X,f.Position.Y)
                    laser.Parent=f;laser.ParentOffset=Vector.Zero;laser.PositionOffset=Vector.Zero
                    laser.CollisionDamage=3.5*f:GetMultiplier()
                    laser:SetMaxDistance(360);laser:SetTimeout(20)
                    local dir=math.abs(face.X)>math.abs(face.Y) and (face.X>0 and Direction.RIGHT or Direction.LEFT)
                        or (face.Y>0 and Direction.DOWN or Direction.UP)
                    f:PlayShootAnim(dir)
                end
            end
        end
    end
end
function W.clear(s)
    for _,entry in ipairs(s.qKnives or {}) do if entry.entity:Exists() then entry.entity:Remove() end end
    s.qKnives=nil
end
function W.hideHeld(knife)
    if knife:GetData().SamiraQAngle~=nil then return false end
    -- Keep the native weapon entity, but do not leave an invisible contact hitbox.
    knife.Visible=false
    knife.CollisionDamage=0
    return true
end
function W.steer(knife,p)
    local data=knife:GetData()
    if not data.SamiraKnifeArt then
        local sprite=knife:GetSprite()
        sprite:ReplaceSpritesheet(0,'gfx/samira/native/effect_momsknife.png');sprite:LoadGraphics()
        data.SamiraKnifeArt=true
    end
    -- Run after the native knife update: Q knives
    -- otherwise inherit the disabled keyboard/head direction each frame.
    -- The emitted face already includes this blade's spread and ground projection.
    -- Never re-aim an airborne knife from the live cursor or player's new facing.
    knife.Rotation=data.SamiraQAngle;knife.RotationOffset=0
    local distance=knife.Position:Distance(p.Position)
    knife.Position=p.Position+Vector(1,0):Rotated(knife.Rotation)*distance
end
function W.update(s)
    for i=#(s.qKnives or {}),1,-1 do
        local entry=s.qKnives[i];local knife=entry.entity;entry.age=entry.age+1
        if not knife:Exists() then table.remove(s.qKnives,i)
        elseif entry.age>=90 or entry.age>2 and not knife:IsFlying() then
            knife:Remove();table.remove(s.qKnives,i)
        else knife.Rotation=entry.angle;knife.RotationOffset=0 end
    end
end
function W.emit(p,s,face,damage,range)
    local I=CollectibleType
    local function has(id)return p:HasCollectible(id) end
    local origin=Vector(p.Position.X,p.Position.Y)
    local scale=damage/math.max(.01,p.Damage)
    local function beam(laser,ticks)
        if not laser then return end
        laser.Position=origin;laser.PositionOffset=Vector.Zero;laser.ParentOffset=Vector.Zero
        laser.DisableFollowParent=true;laser:SetMaxDistance(range);laser:SetTimeout(ticks)
    end
    if has(I.COLLECTIBLE_BRIMSTONE) then beam(p:FireBrimstone(face,p,scale),8) end
    if has(I.COLLECTIBLE_TECHNOLOGY) then
        beam(p:FireTechLaser(origin,LaserOffset.LASER_TECH1_OFFSET,face,false,true,p,scale),4)
    end
    if has(I.COLLECTIBLE_TECHNOLOGY_2) then
        local laser=p:FireTechLaser(origin,LaserOffset.LASER_TECH2_OFFSET,face,true,false,p,1)
        if laser then laser.CollisionDamage=laser.CollisionDamage*scale end
        beam(laser,8)
    end
    if has(I.COLLECTIBLE_TECH_X) then
        local laser=p:FireTechXLaser(origin,face*6,25,p,scale)
        if laser then laser.PositionOffset=Vector.Zero;laser:SetTimeout(math.ceil(range/6)) end
    end
    if has(I.COLLECTIBLE_DR_FETUS) then
        local bomb=p:FireBomb(origin,face*8,p)
        if bomb then bomb.IsFetus=true;bomb:SetExplosionCountdown(30) end
    end
    if has(I.COLLECTIBLE_MOMS_KNIFE) then
        local knife=p:FireKnife(p,0,true,0,0)
        if knife then
            knife.Position=origin;knife.PositionOffset=Vector.Zero
            knife.Rotation=face:GetAngleDegrees();knife.RotationOffset=0;knife.CollisionDamage=damage
            knife:GetData().SamiraQAngle=knife.Rotation
            knife.Visible=true
            knife:Shoot(1,range)
            s.qKnives=s.qKnives or {};s.qKnives[#s.qKnives+1]={entity=knife,angle=knife.Rotation,age=0}
        end
    end
end
return W
