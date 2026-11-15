-- Runtime local-pose blending, hierarchy evaluation, and weighted mesh skinning.
local M={}
-- Resolve the module while the mod's loader context is active, not inside a render callback.
local loaded,data=pcall(include,'scripts.samira_skeleton_data')
local loadError
if not loaded then loadError=tostring(data);data=nil
elseif type(data)~='table' or type(data.vertices)~='table' or type(data.faces)~='table' then
    loadError='model module returned '..type(data)..'; expected vertices/faces tables';data=nil
end
if Isaac and Isaac.DebugString then
    Isaac.DebugString('[Samira skeleton] '..(data and ('loaded '..#data.vertices..' vertices, '..#data.faces..' faces') or loadError))
end
local function mul(a,b)
    local c={}
    for r=0,2 do local k=r*4
        for j=1,3 do c[k+j]=a[k+1]*b[j]+a[k+2]*b[4+j]+a[k+3]*b[8+j] end
        c[k+4]=a[k+1]*b[4]+a[k+2]*b[8]+a[k+3]*b[12]+a[k+4]
    end
    return c
end
local function interpolate(a,b,k,t)
    local v={};for j=1,10 do v[j]=a[k+j]+(b[k+j]-a[k+j])*t end
    local dot=0;for j=4,7 do dot=dot+a[k+j]*b[k+j] end
    if dot<0 then for j=4,7 do v[j]=a[k+j]*(1-t)-b[k+j]*t end end
    return v
end
local function sample(clip,time)
    local phase=(time%clip.duration)/clip.duration*#clip.frames
    local i=math.floor(phase);return clip.frames[i+1],clip.frames[(i+1)%#clip.frames+1],phase-i
end
function M.data()assert(data,loadError);return data end
function M.pose(idleTime,walkTime,blend)
    local d=M.data();local ia,ib,it=sample(d.clips.idle,idleTime);local wa,wb,wt=sample(d.clips.walk,walkTime)
    local worlds={}
    for i,parent in ipairs(d.parents) do
        local k=(i-1)*10;local a=interpolate(ia,ib,k,it);local b=interpolate(wa,wb,k,wt)
        local v=interpolate(a,b,0,blend)
        local x,y,z,w=v[4],v[5],v[6],v[7];local n=math.sqrt(x*x+y*y+z*z+w*w);x=x/n;y=y/n;z=z/n;w=w/n
        local sx,sy,sz=v[8],v[9],v[10]
        local m={(1-2*(y*y+z*z))*sx,2*(x*y-z*w)*sy,2*(x*z+y*w)*sz,v[1],
            2*(x*y+z*w)*sx,(1-2*(x*x+z*z))*sy,2*(y*z-x*w)*sz,v[2],
            2*(x*z-y*w)*sx,2*(y*z+x*w)*sy,(1-2*(x*x+y*y))*sz,v[3]}
        worlds[i]=parent>0 and mul(worlds[parent],m) or m
    end
    local skin={};for i,node in ipairs(d.jointNodes) do skin[i]=mul(worlds[node],d.inverse[i]) end
    return skin
end
function M.vertices(idleTime,walkTime,blend)
    local d=M.data();local matrices=M.pose(idleTime,walkTime,blend);local result={}
    for i,v in ipairs(d.vertices) do
        local x,y,z=v[1],v[2],v[3];local px,py,pz=0,0,0
        for k=6,12,2 do
            local weight=v[k+1]
            if weight>0 then local m=matrices[v[k]]
                px=px+(m[1]*x+m[2]*y+m[3]*z+m[4])*weight
                py=py+(m[5]*x+m[6]*y+m[7]*z+m[8])*weight
                pz=pz+(m[9]*x+m[10]*y+m[11]*z+m[12])*weight
            end
        end
        result[i]={px,py,pz}
    end
    return result
end
return M
