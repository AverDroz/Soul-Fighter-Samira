-- Hide both native tutorial layers; use a room entity independent of backdrop.
local B={};local saved={};local decoration;local variant
local paths={'gfx/samira/branding/controls_hidden.anm2','gfx/samira/branding/buttons_hidden.anm2'}
local function restore()
    for i,entry in pairs(saved) do
        if entry.sprite:GetFilename()==paths[i] and entry.path~='' then
            local frame=entry.sprite:GetFrame()
            entry.sprite:Load(entry.path,true);entry.sprite:SetFrame(entry.animation,frame)
        end
    end
    saved={}
end
function B.reset()
    restore()
    if decoration and decoration:Exists() then decoration:Remove() end
    decoration=nil
end
function B.prepare(room,active)
    if not active then B.reset();return end
    local backdrop=room:GetBackdrop()
    local sprites={backdrop:GetControlsANM2(),backdrop:GetControlsButtonsANM2()}
    for i,sprite in ipairs(sprites) do
        if saved[i] and saved[i].sprite~=sprite then restore();break end
    end
    for i,sprite in ipairs(sprites) do
        if sprite:GetFilename()~=paths[i] then
            local frame=sprite:GetFrame();local animation=sprite:GetAnimation()
            saved[i]={sprite=sprite,path=sprite:GetFilename(),animation=animation}
            sprite:Load(paths[i],true);sprite:SetFrame(animation,frame)
        end
    end
end
function B.update(game,active)
    local level=game:GetLevel()
    local show=active and level:GetAbsoluteStage()==1 and level:GetCurrentRoomIndex()==level:GetStartingRoomIndex()
    if not show then
        if decoration and decoration:Exists() then decoration:Remove() end
        decoration=nil;return
    end
    if decoration and decoration:Exists() then return end
    variant=variant or Isaac.GetEntityVariantByName('Samira Floor Tutorial')
    -- Reuse a decoration restored by the engine after rewind/continue.
    decoration=Isaac.FindByType(EntityType.ENTITY_EFFECT,variant,-1,false,false)[1]
    if not decoration then
        decoration=Isaac.Spawn(EntityType.ENTITY_EFFECT,variant,0,game:GetRoom():GetCenterPos(),Vector.Zero,nil)
    end
    decoration.DepthOffset=-10000
    decoration:GetSprite():SetFrame('Controls',0)
end
return B
