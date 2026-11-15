-- Only hide the duplicate native cursor/stat panel during Samira rendering.
-- Room size, camera, output viewport and mouse coordinates stay native.
local V={};local mouseControl,foundHUD,borderless,configured
function V.fullscreen(active)
    if not active or configured then return end
    configured=true
    if active and Options.UseBorderlessFullscreen==false then
        if borderless==nil then borderless=false end
        local was=Options.Fullscreen
        if was then Options.Fullscreen=false end
        Options.UseBorderlessFullscreen=true
        if was then Options.Fullscreen=true end
    end
end
function V.restore()
    if mouseControl~=nil then Options.MouseControl=mouseControl;mouseControl=nil end
    if foundHUD~=nil then Options.FoundHUD=foundHUD;foundHUD=nil end
end
function V.prepare(active)
    V.restore()
    if active then
        mouseControl=Options.MouseControl;foundHUD=Options.FoundHUD
        Options.MouseControl=false;Options.FoundHUD=false
    end
end
function V.finish()
    V.restore()
    configured=nil
    if borderless~=nil then
        local was=Options.Fullscreen;if was then Options.Fullscreen=false end
        Options.UseBorderlessFullscreen=borderless;borderless=nil
        if was then Options.Fullscreen=true end
    end
end
return V
