-- Keep the native camera following the player after Mother's arena expands.
-- Run from POST_UPDATE: the engine resets the focus each update. Do not move
-- the overlay independently, change CameraStyle, or snap during the intro.
local C={}
function C.update(game,active,frozen)
    if not active or frozen or game:IsPaused() or game:GetNumPlayers()~=1 then return end
    local room=game:GetRoom()
    if room:GetType()~=RoomType.ROOM_BOSS or room:IsClear() then return end
    local p=Isaac.GetPlayer(0)
    if p:IsDead() or not p.ControlsEnabled then return end
    -- 912.10 is the moving second-phase body; 912.0 also remains in the room.
    -- Checking the body avoids overriding the first phase and arena opening.
    for _,e in ipairs(Isaac.FindByType(EntityType.ENTITY_MOTHER,10,-1,false,false)) do
        local npc=e:ToNPC()
        if npc and not npc:IsDead() and npc:IsActiveEnemy(false)
            and not npc:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
            and npc.State>=NpcState.STATE_IDLE then
            room:GetCamera():SetFocusPosition(p.Position)
            return
        end
    end
end
return C
