local G=include('scripts.samira_geometry')
local T={}
local function animation(entity)
    local sprite=entity.GetSprite and entity:GetSprite()
    return sprite and sprite:GetAnimation() or ''
end
function T.fire(e)
    if not e or e.Type~=EntityType.ENTITY_FIREPLACE or not e:Exists() or e:IsDead() or (e.HitPoints or 0)<=0 then return false end
    local anim=animation(e)
    return not (anim:match('^NoFire') or anim:match('^Dissapear') or anim:match('^Disappear'))
end
function T.poop(room,index)
    if index==nil then return end
    local grid=room:GetGridEntity(index)
    if grid and grid:GetType()==GridEntityType.GRID_POOP and (grid.State or 0)<1000
        and grid.CollisionClass~=GridCollisionClass.COLLISION_NONE and animation(grid)~='State5' then return grid end
end
function T.poopAt(room,pos)
    local index=room:GetGridIndex(pos)
    if T.poop(room,index) then return index end
end
function T.walkable(room,p,index)
    local collision=room:GetGridCollision(index)
    return collision==GridCollisionClass.COLLISION_NONE
        or p.CanFly and collision<GridCollisionClass.COLLISION_WALL
end
function T.lineClear(room,p,from,to)
    if not p.CanFly then return room:CheckLine(from,to,0,0,false,false) end
    -- Native CheckLine modes all include some ground obstacles. Flying only
    -- needs room bounds/walls; sample at sub-tile spacing, including the target.
    local delta=to-from;local steps=math.max(1,math.ceil(delta:Length()/8))
    for i=0,steps do
        local point=from+delta*(i/steps)
        if not room:IsPositionInRoom(point,0) or not T.walkable(room,p,room:GetGridIndex(point)) then return false end
    end
    return true
end
function T.clear(room,p,pos)
    local radius=math.max(10,p.Size or 12)
    if not room:IsPositionInRoom(pos,radius) then return false end
    for i=0,8 do
        local sample=pos+(i==0 and Vector.Zero or Vector(radius,0):Rotated((i-1)*45))
        if not T.walkable(room,p,room:GetGridIndex(sample)) then return false end
    end
    return true
end
function T.destination(room,p,face,length)
    local origin=p.Position
    local function point(distance)return origin+G.project(face*distance)end
    -- Never cross the room perimeter or an actual wall/closed doorway.
    local limit=G.dashTerrainRange
    for distance=2,limit,2 do
        local pos=point(distance);local c=room:GetGridCollision(room:GetGridIndex(pos))
        if not room:IsPositionInRoom(pos,math.max(10,p.Size or 12)) or c==GridCollisionClass.COLLISION_WALL then limit=distance-2;break end
    end
    local wanted=math.min(length,limit)
    if wanted>=4 and T.clear(room,p,point(wanted)) then return point(wanted),wanted end
    -- If the requested landing is inside terrain, extend only far enough to get across.
    for distance=wanted+2,limit,2 do
        if T.clear(room,p,point(distance)) then return point(distance),distance end
    end
    for distance=wanted-2,4,-2 do
        if T.clear(room,p,point(distance)) then return point(distance),distance end
    end
end
function T.begin(room,p,s,face,length)
    local target,distance=T.destination(room,p,face,length)
    if not target then return false end
    s.dash={face=face,origin=Vector(p.Position.X,p.Position.Y),target=target,safe=Vector(p.Position.X,p.Position.Y),
        age=0,duration=math.ceil(math.min(length,G.dashRange)/G.dashStep),left=distance,collision=p.GridCollisionClass,flying=p.CanFly==true}
    p.GridCollisionClass=EntityGridCollisionClass.GRIDCOLL_WALLS
    return true
end
function T.finish(p,s,relocate)
    local d=s.dash;if not d then return end
    if relocate then p.Position=d.safe end
    p.GridCollisionClass=p.CanFly and EntityGridCollisionClass.GRIDCOLL_WALLS
        or d.flying and EntityGridCollisionClass.GRIDCOLL_GROUND or d.collision
    p.Velocity=Vector.Zero;s.dash=nil;s.dashStop=true
end
function T.update(room,p,s)
    local d=s.dash;d.age=d.age+1
    p.Position=d.origin+(d.target-d.origin)*math.min(1,d.age/d.duration)
    p.Velocity=Vector.Zero
    if T.clear(room,p,p.Position) then d.safe=Vector(p.Position.X,p.Position.Y) end
    if d.age>=d.duration then T.finish(p,s,true) end
end
function T.smash(room,p,face,shape)
    local center=p.Position+G.project(face*shape.cx)
    -- Run the native explosion package once: doors, chests, slots, statues,
    -- tinted rocks and TNT retain their own rules and chain reactions.
    local data=p:GetData();local previous=data.SamiraTerrainExplosion
    data.SamiraTerrainExplosion=true
    local ok,err=pcall(function()
        Game():BombExplosionEffects(center,100,0,Color.Default,p,shape.radius/75,false,false,DamageFlag.DAMAGE_EXPLOSION)
    end)
    data.SamiraTerrainExplosion=previous
    if not ok then error(err) end
end
function T.blockExplosionDamage(entity,flags,source)
    local owner=source and source.Entity
    if not owner or not owner:GetData().SamiraTerrainExplosion or (flags & DamageFlag.DAMAGE_EXPLOSION)==0 then return false end
    -- Q3 itself already applies combat damage. Keep this explosion environmental;
    -- secondary TNT/bomb-rock explosions have their own sources and still work.
    return entity:ToPlayer()~=nil or entity.Type~=EntityType.ENTITY_FIREPLACE and entity:IsVulnerableEnemy()
end
function T.basicTarget(room,p,face,reach,thrust)
    local target,nearest=nil,math.huge
    for index=0,room:GetGridSize()-1 do
        local grid=T.poop(room,index)
        if grid then
            local delta=G.unproject(grid.Position-p.Position):Rotated(-face:GetAngleDegrees())
            local distance=G.basicContact(delta.X,delta.Y,0,reach,thrust)
            if distance and distance<nearest then target=grid;nearest=distance end
        end
    end
    return target,nearest
end
function T.qHit(room,p,face,shape,stage,entities)
    local hits=stage==3 and 3 or 2
    for index=0,room:GetGridSize()-1 do
        local grid=T.poop(room,index)
        if grid then
            local delta=G.unproject(grid.Position-p.Position):Rotated(-face:GetAngleDegrees())
            if G.hit(shape,delta.X,delta.Y,0) then grid:Hurt(hits) end
        end
    end
    for _,e in ipairs(entities) do
        if T.fire(e) then
            local delta=G.unproject(e.Position-p.Position):Rotated(-face:GetAngleDegrees())
            if G.hit(shape,delta.X,delta.Y,e.Size) then e:TakeDamage(math.max(0,p.Damage)*hits,0,EntityRef(p),0) end
        end
    end
    if stage==3 then T.smash(room,p,face,shape) end
end
return T
