import random

# --- Phase pools by boss tier ---
# Each tier uses a different subset/ordering of mini-games.

QUEST_BOSS_PHASES = [
    {
        "name": "Barrage",
        "minigame": "dodge",
        "telegraph": "opens fire!",
        "tip": "Dodge the projectiles! Arrow keys to move!",
    },
    {
        "name": "Exposed",
        "minigame": "timing_strike",
        "telegraph": "is overheated and vulnerable!",
        "tip": "Time your strikes! Hit the green zone!",
    },
]

RETALIATION_BOSS_PHASES = [
    {
        "name": "Charging",
        "minigame": "chase",
        "telegraph": "revs its engine and accelerates away!",
        "tip": "Chase it down! Switch lanes to dodge obstacles!",
    },
    {
        "name": "Barrage",
        "minigame": "dodge",
        "telegraph": "opens fire with everything it has!",
        "tip": "Dodge the projectiles! Arrow keys to move!",
    },
    {
        "name": "Exposed",
        "minigame": "timing_strike",
        "telegraph": "is overheated and its armor is glowing!",
        "tip": "Time your strikes! Hit the green zone!",
    },
]

COUP_BOSS_PHASES = [
    {
        "name": "Charging",
        "minigame": "chase",
        "telegraph": "revs its engine and accelerates away!",
        "tip": "Chase it down! Switch lanes to dodge obstacles!",
    },
    {
        "name": "Barrage",
        "minigame": "dodge",
        "telegraph": "unleashes a hail of fire!",
        "tip": "Dodge the projectiles! Arrow keys to move!",
    },
    {
        "name": "Shielded",
        "minigame": "guard_break",
        "telegraph": "raises its deflector shields!",
        "tip": "Fire through the gap in the rotating shield!",
    },
    {
        "name": "Barrage II",
        "minigame": "dodge",
        "telegraph": "enters a berserk rage and fires wildly!",
        "tip": "Dodge everything! This is the hard one!",
    },
    {
        "name": "Exposed",
        "minigame": "timing_strike",
        "telegraph": "is overheated — now or never!",
        "tip": "Time your strikes! Hit the green zone!",
    },
    {
        "name": "Shielded II",
        "minigame": "guard_break",
        "telegraph": "reinforces its shields for a final stand!",
        "tip": "Fire through the gap — it's spinning faster!",
    },
]

APEX_BOSS_PHASES = [
    {
        "name": "Annihilation",
        "minigame": "dodge",
        "telegraph": "unleashes an apocalyptic barrage!",
        "tip": "Survive this! Everything is coming at you!",
    },
    {
        "name": "Pursuit",
        "minigame": "chase",
        "telegraph": "guns the engine and tries to shake you!",
        "tip": "Stay on target! Close the gap!",
    },
    {
        "name": "Fortress",
        "minigame": "guard_break",
        "telegraph": "deploys layered shield arrays!",
        "tip": "Find the gap — it's narrow and fast!",
    },
    {
        "name": "Core Exposed",
        "minigame": "timing_strike",
        "telegraph": "— its core is exposed! Strike NOW!",
        "tip": "Every hit counts! Time them perfectly!",
    },
    {
        "name": "Annihilation II",
        "minigame": "dodge",
        "telegraph": "enters a berserk frenzy!",
        "tip": "This is worse than before! Stay alive!",
    },
    {
        "name": "Final Shield",
        "minigame": "guard_break",
        "telegraph": "channels everything into one last barrier!",
        "tip": "Break through! This is the end!",
    },
    {
        "name": "Death Blow",
        "minigame": "timing_strike",
        "telegraph": "— its armor cracks! Finish it!",
        "tip": "Make every shot count!",
    },
]

BOSS_TIER_PHASES = {
    "quest": QUEST_BOSS_PHASES,
    "retaliation": RETALIATION_BOSS_PHASES,
    "coup": COUP_BOSS_PHASES,
    "apex": APEX_BOSS_PHASES,
}

BOSS_TIER_SCALING = {
    "quest": {"hp_mult": 1.0, "dmg_mult": 1.0},
    "retaliation": {"hp_mult": 2.0, "dmg_mult": 1.5},
    "coup": {"hp_mult": 4.0, "dmg_mult": 2.5},
    "apex": {"hp_mult": 8.0, "dmg_mult": 4.0},
}

# Fallback if no tier is set
DEFAULT_PHASES = RETALIATION_BOSS_PHASES


def get_phases_for_boss(game_state):
    tier = getattr(game_state, "boss_tier", "retaliation")
    return BOSS_TIER_PHASES.get(tier, DEFAULT_PHASES)


def get_current_phase(game_state):
    phases = get_phases_for_boss(game_state)
    idx = getattr(game_state, "boss_phase_index", 0)
    return phases[idx % len(phases)]


def advance_phase(game_state):
    phases = get_phases_for_boss(game_state)
    game_state.boss_phase_index = (getattr(game_state, "boss_phase_index", 0) + 1) % len(phases)
    return get_current_phase(game_state)


def check_combat_end(game_state):
    if game_state.combat_enemy.durability <= 0:
        return "victory"
    if game_state.current_durability <= 0:
        return "defeat"
    return None
