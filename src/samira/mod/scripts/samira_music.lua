-- Own only the temporary R track; never change the user's music-volume option.
local M={};local track;local previous;local queued;local boostedVolume
local function musicId()
    if not track then track=Isaac.GetMusicIdByName('Samira World Ender') end
    return track
end
function M.start()
    local id=musicId();if not id or id<=0 then return end
    local manager=MusicManager()
    if previous==nil then
        previous=manager:GetCurrentMusicID();queued=manager:GetQueuedMusicID()
        manager:Play(id,1);manager:Queue(id);manager:UpdateVolume()
    end
    -- UpdateVolume restores the options slider; boost only this temporary track.
    -- Preserve mute, avoid clipping, and follow changes made in the options menu.
    local volume=math.min(1,math.max(0,Options.MusicVolume)*3)
    if manager:GetCurrentMusicID()==id and boostedVolume~=volume then
        manager:VolumeSlide(volume,.12);boostedVolume=volume
    end
end
function M.beforePlay(id)
    if previous==nil or id==track then return end
    -- Room/boss music changes still determine what should play when R ends.
    previous=id;queued=id
    return false
end
function M.stop()
    if previous==nil then return end
    local manager=MusicManager();local restore=previous;local nextTrack=queued
    local pending=manager:GetQueuedMusicID()
    if pending~=track and pending>=0 then nextTrack=pending end
    previous=nil;queued=nil;boostedVolume=nil
    -- Do not overwrite music another system already took ownership of.
    if manager:GetCurrentMusicID()~=track then return end
    if restore>0 then manager:Crossfade(restore,.12);manager:UpdateVolume()
    else manager:Fadeout(.12) end
    manager:Queue(nextTrack or restore)
end
return M
