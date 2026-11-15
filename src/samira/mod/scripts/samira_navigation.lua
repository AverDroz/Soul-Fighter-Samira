-- Four-neighbour BFS only when a click/target requires a new path, not per render.
local N={}
-- Click the visible door area, including its frame, rather than a single floor cell.
function N.exit(room,destination)
    local best,bestDistance
    for slot=0,7 do
        local door=room:GetDoor(slot)
        if door then
            local side=slot%4;local normal=({Vector(-1,0),Vector(0,-1),Vector(1,0),Vector(0,1)})[side+1]
            local d=destination-door.Position;local forward=d.X*normal.X+d.Y*normal.Y
            local lateral=math.abs(d.X*normal.Y-d.Y*normal.X)
            if forward>=-48 and forward<=96 and lateral<44 then
                local distance=d:Length()
                if not bestDistance or distance<bestDistance then best={door.Position,normal,door,slot};bestDistance=distance end
            end
        end
    end
    if best then return table.unpack(best) end
end
function N.atDoor(position,opening,normal)
    local d=opening-position;local forward=d.X*normal.X+d.Y*normal.Y
    return forward>=-8 and forward<=46 and math.abs(d.X*normal.Y-d.Y*normal.X)<=14
end
function N.enter(game,player,s,door,slot)
    if not door:IsOpen() or door:IsLocked() or door.TargetRoomIndex==nil then return false end
    -- Spiked thresholds retain native collision/damage handling.
    if door:IsRoomType(RoomType.ROOM_CURSE) then return false end
    local level=game:GetLevel();s.departing=Isaac.GetTime()+1500
    level.LeaveDoor=slot
    Isaac.DebugString('[Samira door] transition slot='..slot..' target='..door.TargetRoomIndex)
    game:StartRoomTransition(door.TargetRoomIndex,slot%4,RoomTransitionAnim.WALK,player,level:GetDimension())
    return true
end
function N.path(start,goal,width,count,walkable)
    if start==goal then return {} end
    local queue={start};local head=1;local previous={[start]=start};local best=start
    local function dist(i)return math.abs(i%width-goal%width)+math.abs(math.floor(i/width)-math.floor(goal/width)) end
    while queue[head] do
        local current=queue[head];head=head+1
        if dist(current)<dist(best) then best=current end
        if current==goal then best=current;break end
        for _,nextIndex in ipairs({current-1,current+1,current-width,current+width}) do
            if nextIndex>=0 and nextIndex<count and previous[nextIndex]==nil
                and math.abs(nextIndex%width-current%width)+math.abs(math.floor(nextIndex/width)-math.floor(current/width))==1
                and walkable(nextIndex) then
                previous[nextIndex]=current;queue[#queue+1]=nextIndex
            end
        end
    end
    local route={};while best~=start do table.insert(route,1,best);best=previous[best] end
    return route
end
return N
