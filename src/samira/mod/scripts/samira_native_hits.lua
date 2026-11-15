-- Native on-hit status rolls, without spawning an invisible extra damage tear.
local N={}
local mask=TearFlags.TEAR_POISON | TearFlags.TEAR_SLOW | TearFlags.TEAR_FREEZE
    | TearFlags.TEAR_CHARM | TearFlags.TEAR_CONFUSION | TearFlags.TEAR_FEAR
    | TearFlags.TEAR_BURN | TearFlags.TEAR_MIDAS | TearFlags.TEAR_GISH
    | TearFlags.TEAR_PERMANENT_CONFUSION | TearFlags.TEAR_GODS_FLESH
    | TearFlags.TEAR_MAGNETIZE | TearFlags.TEAR_BAIT
function N.apply(p,e)
    if not e:Exists() or e:IsDead() then return end
    local npc=e:ToNPC()
    if not npc or e.Type==EntityType.ENTITY_FIREPLACE then return end
    -- One roll per accepted victim/attack. The engine owns luck and immunity.
    local params=p:GetTearHitParams(WeaponType.WEAPON_TEARS,1,1,p)
    local flags=params.TearFlags & mask
    if flags~=TearFlags.TEAR_NORMAL then
        npc:ApplyTearflagEffects(e.Position,flags,p,p:GetTearPoisonDamage())
    end
end
return N
