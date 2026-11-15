-- Use the explicit factory and setters: avoid the failing callable quad constructor.
local Q={}
function Q.set(q,a,b,c,d)
    q:SetTopLeft(a);q:SetTopRight(b);q:SetBottomLeft(c);q:SetBottomRight(d)
    return q
end
function Q.source(a,b,c,d)
    return Q.set(SourceQuad.NewFromRectangle(Vector.Zero,1,1,true),a,b,c,d)
end
function Q.destination(a,b,c,d)
    return Q.set(DestinationQuad.NewFromRectangle(Vector.Zero,1,1),a,b,c,d)
end
return Q
