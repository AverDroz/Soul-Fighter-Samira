"""Create an uninstalled reference fork; this does not implement Samira."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / 'vendor/herostudio/Hero-Studio-0.2.33'
sys.dont_write_bytecode = True
sys.path.insert(0, str(STUDIO / 'app'))
import project
import scaffold


def main():
    authoring = ROOT / 'authoring'
    destination = ROOT / 'src/samira'
    if destination.exists() or (authoring / 'hero.project.json').exists():
        raise SystemExit('Existing project preserved; bootstrap is for first creation only.')
    profile = project.new_profile('samira', 'Samira')
    profile.update(version='0.0.1',
        description='Planning scaffold. Samira assets and gameplay are NOT implemented.',
        source_credit='Riot Games: League of Legends character assets (not yet imported). TFOS4: Isaac-LoL-HeroStudio reference framework.',
        equipment={'mode': 'custom', 'selected': []},
        project_status={'phase': 'source_audit', 'playable': False,
            'numeric_values_are_placeholders': True,
            'equipment_selection': 'all_suitable_items_as_isaac_stats',
            'asset_import': 'pending_client_or_asset_package'})
    profile['stats']['resource'] = 'none'
    profile['project_status'].update(
        scope='personal_fun_mod',
        shop='native_isaac_room_10_to_15_random_offers',
        augments='arena_catalog_adapted_via_isaac_effects',
        imported_shop_enabled=False,
        six_slot_equipment_required=False)
    profile['integration'] = {'status': 'not_implemented', 'base': 'aatrox_reference',
        'notes': 'Reference fork only. No Samira model, style, ranged attacks, skills or augments yet.'}
    notes = {
        'Q': ('Flair', 'projectile', 'Directional shot / close-range blade. User described empowered attack; exact variant remains a design decision.'),
        'W': ('Blade Whirl', 'area', 'Circular damage and projectile destruction. Laser interaction requires a deliberate rule.'),
        'E': ('Wild Rush', 'dash', 'Targeted dash, collision handling and kill reset adaptation.'),
        'R': ('Inferno Trigger', 'area', 'Ten damage waves around Samira, gated by S style. Combo and item rules must be implemented.')}
    for key, (name, kind, note) in notes.items():
        profile['abilities'][key].update(name=name, kind=kind,
            notes='NOT IMPLEMENTED; numeric fields are editor placeholders. ' + note)
    project.write(authoring / 'hero.project.json', profile)
    project.generate_handoff(authoring, profile)
    result = scaffold.generate(STUDIO / 'reference-framework', authoring, profile, destination)
    # The shipped source scaffold omits this dependency used by its equipment kit.
    balance = (STUDIO / 'app/equipment-reference/aatrox_balance.lua').read_text('utf8')
    balance = balance.replace('[Aatrox config]', '[Samira config]').replace('aatrox_config', 'samira_config')
    (destination / 'mod/scripts/samira_balance.lua').write_text(
        '-- Reference balance adapter, NOT tuned for Samira.\n' + balance, encoding='utf8')
    (destination / 'mod/samira_config.lua').write_text(
        '-- Reference defaults only. Samira combat is not implemented yet.\nreturn {}\n', encoding='utf8')
    report = project.validate(profile, authoring)
    project.write(ROOT / 'docs/authoring-validation.json', report)
    print(json.dumps({'generated': result, 'playable': False,
        'errors': report['errors'], 'warnings': report['warnings']}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
