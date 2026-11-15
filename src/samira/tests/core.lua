local G=include('scripts.samira_geometry');local N=include('scripts.samira_navigation')
local s=G.shape(1);assert(G.hit(s,170,0,0));assert(not G.hit(s,190,0,0));assert(not G.hit(s,50,30,0))
local yes,sweet=G.hit(s,160,0,0);assert(yes and sweet);yes,sweet=G.hit(s,45,0,0);assert(yes and not sweet)
assert(math.abs(G.dashRange/s.far-330/650)<.00001,'E and Q use one world scale')
s=G.shape(2);assert(G.hit(s,140,65,0));assert(not G.hit(s,-25,60,0));assert(not G.hit(s,160,0,0))
s=G.shape(3);yes,sweet=G.hit(s,56,0,0);assert(yes and sweet);yes,sweet=G.hit(s,130,0,0);assert(yes and not sweet)
assert(not G.hit(s,-40,0,0))
for kind,contact in pairs({Q1=.60,Q2=.82,Q3=.53,RQ1=.60,RQ2=.56,RQ3=.53}) do
 local c={age=18,impact=18,duration=24};assert(math.abs(G.castPhase(kind,c)-contact)<.00001,'damage and sword contact must coincide')
 local previous=0
 for frame=0,48 do c.age=frame/2;local phase=G.castPhase(kind,c);assert(phase>=previous and phase<=1);previous=phase end
end
local a=G.stats(3.5,10,260,0,1);local b=G.stats(3.5,10,460,10,1)
assert(b.reach>a.reach and b.scale>a.scale and b.crit==.4)
assert(G.stats(3.5,-1,100000,1000,100).crit<=.6 and G.stats(3.5,-1,100000,1000,100).reach<=90)
local route=N.path(0,4,5,25,function(i)return i~=2 end);assert(route[#route]==4)
for i,v in ipairs(route) do assert(v~=2);local last=route[i-1] or 0;assert(math.abs(v%5-last%5)+math.abs(math.floor(v/5)-math.floor(last/5))==1) end
route=N.path(0,24,5,25,function(i)return i<5 end);assert(route[#route]==4)
print('Geometry, sweet spots, stat caps and obstacle routing passed')
