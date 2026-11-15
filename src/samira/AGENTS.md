# Hero template development rules

- Read README-AGENT.md and hero.json (in generated projects) before editing.
- Work in the generated project. Never patch the author's game paths or original Aatrox project.
- Reuse original game UI and VFX assets unless the user explicitly authorizes new artwork. If required assets are missing, report the exact gap; do not silently substitute drawn effects.
- The generated reference still implements Aatrox. Namespacing alone does not implement another hero.
- Do not globally replace `aatrox`: source animation names, particle keys and textures may intentionally retain that string.
- Keep damage, cooldowns, inventory, saving and input authoritative in Lua. Rendering must not perform a second damage calculation.
- Continuous mana regeneration is normal rate x3 x current ShotSpeed; rage gain is its hero-specific base x current ShotSpeed. Use scripts.hero_balance once per 30 Hz tick (or once per rage-generating event), preserving fractions and resource caps. See docs/RESOURCE-BALANCE.md. Do not double-scale, advance while paused, scale instant mana restores/costs, or add mana to manaless heroes.
- Preserve session/room/heartbeat ownership and native fallback. Do not fix a flicker by forcing the actor visible over cutscenes.
- Avoid broad input interception: native drop/swap, pause, active items, bombs and controller controls must remain compatible.
- Do not use kill-all Python/game processes, reboot, global cursor replacement or destructive cleanup as a development shortcut.
- Do not install or launch on a guessed game path. Use the user's explicit path and close the game before updating.
- Match work to task size. Reuse assets, avoid repeated baking or unnecessary agents. Explain material scope/cost growth before proceeding.
- Run relevant tests and report what was actually verified. Unit/offscreen tests are not a substitute for live game testing.
- Keep source attribution and third-party license files. Do not invent a blanket license for bundled game assets.

Read docs/RUNTIME-PITFALLS.md before adapting camera, mirror coordinates, knock-up, summon/save/rewind, shop or release behavior. Preserve existing Companion compatibility; do not silently require players to reinstall it.
