-- The external overlay bypasses Isaac's mirrored room compositor.
-- Transform presentation only; gameplay, HUD and physical cursor stay unchanged.
local S={}
function S.mirror(payload)
    local width=payload.screen[1]
    local function point(p)if p then p[1]=width-p[1] end end
    local function object(v)
        if not v then return end
        for _,key in ipairs({'position','origin','anchor','target'}) do point(v[key]) end
        if v.face then v.face[1]=-v.face[1] end
        for _,f in ipairs(v.faces or {}) do f[1]=-f[1] end
    end
    object(payload);object(payload.cast)
    for _,key in ipairs({'fx','hits','goldFX','heartsteel','heartsteelHits'}) do
        for _,v in ipairs(payload[key] or {}) do object(v) end
    end
    for _,key in ipairs({'mastery','bolt','chain','dash','click','redemption'}) do object(payload[key]) end
    return payload
end
return S
