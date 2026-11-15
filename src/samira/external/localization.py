"""Game-selected UI language; source/client item names remain available in both languages."""
EN={'装备商店':'Equipment shop','金币':'coins','出售':'Sell','购买':'Buy','无基础属性':'No base stats','可合成':'Builds into',
    '撤回':'Undo','无法撤回':'Nothing to undo','已撤回交易':'Transaction undone',
    '基础装备':'BASIC ITEMS','中级装备':'EPIC ITEMS','高级装备':'LEGENDARY ITEMS','全部装备':'ALL ITEMS',
    '品质':'Quality','原版属性（EID）':'Original stats (EID)','原版效果（EID）':'Original effects (EID)',
    '原版效果':'Original effects','暂无详细描述':'No detailed description available','Samira适配：':'Samira: ',
    '原版说明供参考，实际按本Mod的技能与生命规则结算。':'Original reference; this mod\'s skill and health rules determine the actual behavior.',
    '适配：':'Effect: ','合成：':'Builds from: ','合成':'Combine','已抵扣':'Owned credit','永久生命':'stacked health','战斗中无法交易':'Cannot trade during combat',
    '金币不足':'Not enough coins','买入成功':'Purchased','售出成功':'Sold','不可出售':'Cannot sell',
    '装备栏已满':'Inventory full','已拥有不可重复购买':'Already owned; cannot buy duplicates','已拥有该装备':'Already owned','不可购买':'Unavailable',
    '生命':'Health','攻击力':'Attack damage','法强':'Ability power','护甲':'Armor','魔抗':'Magic resist',
    '攻速':'Attack speed','暴击':'Crit chance','技能急速':'Ability haste','移速':'Move speed',
    '生命偷取':'Life steal','全能吸血':'Omnivamp','法力':'Mana','生命回复':'Health regen',
    '法力回复':'Mana regen','护甲穿透':'Armor penetration','法术穿透':'Magic penetration',
    '穿甲':'Lethality','治疗护盾':'Heal/shield power','韧性':'Tenacity','暴击伤害':'Crit damage'}
NOTES={1055:'Attack damage, health and a small amount of basic-attack healing.',1001:'Increases movement speed.',
       1036:'Increases attack damage.',1028:'Increases maximum health without refilling missing health.',1042:'Increases attack speed.',
       6333:'Defers part of incoming damage. A boss takedown cleanses the deferred damage and heals you.',
       3161:'Ability haste. Spell hits build stacks that increase spell damage.',6610:'The first attack against each target critically strikes and heals you. Each target has its own cooldown.',
       2501:'Gain attack damage from bonus health, with more attack damage at low health.',3071:'Physical hits shred armor in stacks and grant movement speed.'}
def translate(text,language):return EN.get(text,text) if language=='en' else text
