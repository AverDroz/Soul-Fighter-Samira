"""Keep the screen HUD independent of room-local actor visibility."""
def layers(state):
    if not state:return False,False
    if state.get('presentation',0)>=2:
        return not state.get('occluded',False),bool(state.get('hudVisible',True))
    paused=state.get('paused',False)
    actor=not (paused or state.get('transition') or state.get('occluded') or state.get('positionReset'))
    hud=state.get('hudVisible',not (paused or state.get('occluded')))
    return actor,bool(hud and (not paused or state.get('transition')))
