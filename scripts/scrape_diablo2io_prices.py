#!/usr/bin/env python3
"""Scrape diablo2.io price check pages for real trade prices.

Fetches recent completed trades from diablo2.io, extracts rune-based payments,
converts to FG using our existing rune->fg rates, and inserts as observed_prices.

Usage:
    PYTHONPATH=src python3 scripts/scrape_diablo2io_prices.py --db data/cache/d2lut.db
    PYTHONPATH=src python3 scripts/scrape_diablo2io_prices.py --db data/cache/d2lut.db --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# diablo2.io item_id -> (canonical_item_id, display_name)
# Extracted from diablo2.io /uniques page URL patterns: /uniques/name-tNNN.html
# Only items that are actually tradeable and missing from our d2jsp corpus.
# ---------------------------------------------------------------------------
D2IO_ITEMS: list[dict] = [
    # ---- HIGH tier uniques ----
    {"d2io_id": 1002, "canonical": "unique:tyraels_might", "name": "Tyrael's Might"},
    {"d2io_id": 1023, "canonical": "unique:wisp_projector", "name": "Wisp Projector"},
    {"d2io_id": 859, "canonical": "unique:metalgrid", "name": "Metalgrid"},
    {"d2io_id": 870, "canonical": "unique:ormus_robes", "name": "Ormus' Robes"},
    {"d2io_id": 854, "canonical": "unique:archon_staff", "name": "Mang Song's Lesson"},
    # ---- MED tier uniques ----
    {"d2io_id": 673, "canonical": "unique:balrog_skin", "name": "Arkaine's Valor"},
    {"d2io_id": 905, "canonical": "unique:mesh_armor", "name": "Shaftstop"},
    {"d2io_id": 716, "canonical": "unique:balista", "name": "Buriza-Do Kyanon"},
    {"d2io_id": 915, "canonical": "unique:battle_belt", "name": "Snowclash"},
    {"d2io_id": 1007, "canonical": "unique:grim_helm", "name": "Vampire Gaze"},
    {"d2io_id": 868, "canonical": "unique:vampirefang_belt", "name": "Nosferatu's Coil"},
    {"d2io_id": 997, "canonical": "unique:cryptic_axe", "name": "Tomb Reaver"},
    {"d2io_id": 943, "canonical": "unique:scourge", "name": "Stormlash"},
    {"d2io_id": 937, "canonical": "unique:legendary_mallet", "name": "Stone Crusher"},
    {"d2io_id": 808, "canonical": "unique:mighty_scepter", "name": "Heaven's Light"},
    {"d2io_id": 742, "canonical": "unique:berserker_axe", "name": "Death Cleaver"},
    {"d2io_id": 672, "canonical": "unique:hyperion_spear", "name": "Arioc's Needle"},
    {"d2io_id": 711, "canonical": "unique:lich_wand", "name": "Boneshade"},
    {"d2io_id": 869, "canonical": "unique:elder_staff", "name": "Ondal's Wisdom"},
    {"d2io_id": 889, "canonical": "unique:quarterstaff", "name": "Ribcracker"},
    {"d2io_id": 902, "canonical": "unique:myrmidon_greaves", "name": "Shadow Dancer"},
    {"d2io_id": 900, "canonical": "unique:legendary_mallet", "name": "Schaefer's Hammer"},
    {"d2io_id": 963, "canonical": "unique:thunder_maul", "name": "Cranium Basher"},
    {"d2io_id": 971, "canonical": "unique:wire_fleece", "name": "Gladiator's Bane"},
    {"d2io_id": 957, "canonical": "unique:sacred_armor", "name": "Templar's Might"},
    {"d2io_id": 710, "canonical": "unique:ogre_axe", "name": "Bonehew"},
    {"d2io_id": 753, "canonical": "unique:champion_sword", "name": "Doombringer"},
    {"d2io_id": 681, "canonical": "unique:phase_blade", "name": "Azurewrath"},
    {"d2io_id": 720, "canonical": "unique:ring", "name": "Carrion Wind"},
    {"d2io_id": 863, "canonical": "unique:ring", "name": "Nature's Peace"},
    {"d2io_id": 960, "canonical": "unique:amulet", "name": "The Cat's Eye"},
    {"d2io_id": 966, "canonical": "unique:amulet", "name": "Eye of Etlich"},
    {"d2io_id": 41, "canonical": "unique:amulet", "name": "Seraph's Hymn"},
    {"d2io_id": 1006, "canonical": "unique:winged_helm", "name": "Valkyrie Wing"},
    {"d2io_id": 735, "canonical": "unique:grand_crown", "name": "Crown of Thieves"},
    {"d2io_id": 929, "canonical": "unique:casque", "name": "Stealskull"},
    {"d2io_id": 1029, "canonical": "unique:fury_visor", "name": "Wolfhowl"},
    {"d2io_id": 708, "canonical": "unique:succubus_skull", "name": "Boneflame"},
    {"d2io_id": 1020, "canonical": "unique:rogue_bow", "name": "Widowmaker"},
    {"d2io_id": 1022, "canonical": "unique:ogre_maul", "name": "Windhammer"},
    {"d2io_id": 898, "canonical": "unique:scarabshell_boots", "name": "Sandstorm Trek"},
    {"d2io_id": 1019, "canonical": "unique:sharkskin_boots", "name": "Waterwalk"},
    {"d2io_id": 906, "canonical": "unique:mesh_boots", "name": "Silkweave"},
    {"d2io_id": 896, "canonical": "unique:ettin_axe", "name": "Rune Master"},
    {"d2io_id": 695, "canonical": "unique:tulwar", "name": "Blade of Ali Baba"},
    {"d2io_id": 878, "canonical": "unique:mage_plate", "name": "Que-Hegan's Wisdom"},
    {"d2io_id": 685, "canonical": "unique:greater_talons", "name": "Bartuc's Cut-Throat"},
    {"d2io_id": 1001, "canonical": "unique:studded_leather", "name": "Twitchthroe"},
    {"d2io_id": 702, "canonical": "unique:heavy_gloves", "name": "Bloodfist"},
    {"d2io_id": 894, "canonical": "unique:war_hat", "name": "Rockstopper"},
    {"d2io_id": 871, "canonical": "unique:war_hat", "name": "Peasant Crown"},
    {"d2io_id": 887, "canonical": "unique:sharkskin_belt", "name": "Razortail"},
    {"d2io_id": 886, "canonical": "unique:tomahawk", "name": "Razor's Edge"},
    {"d2io_id": 947, "canonical": "unique:giant_thresher", "name": "Stormspire"},
    {"d2io_id": 676, "canonical": "unique:caduceus", "name": "Astreon's Iron Ward"},
    {"d2io_id": 684, "canonical": "unique:devil_star", "name": "Baranar's Star"},
    {"d2io_id": 721, "canonical": "unique:blood_spirit", "name": "Cerebus' Bite"},
    {"d2io_id": 731, "canonical": "unique:war_spike", "name": "Cranebeak"},
    {"d2io_id": 747, "canonical": "unique:tyrant_club", "name": "Demon Limb"},
    {"d2io_id": 757, "canonical": "unique:dusk_shroud", "name": "Duriel's Shell"},
    {"d2io_id": 758, "canonical": "unique:champion_axe", "name": "Ethereal Edge"},
    {"d2io_id": 770, "canonical": "unique:gauntlets", "name": "Frostburn"},
    {"d2io_id": 774, "canonical": "unique:bone_visage", "name": "Giant Skull"},
    {"d2io_id": 776, "canonical": "unique:war_gauntlets", "name": "Gravepalm"},
    {"d2io_id": 780, "canonical": "unique:corona", "name": "Guardian Angel"},
    {"d2io_id": 814, "canonical": "unique:decapitator", "name": "Hellslayer"},
    {"d2io_id": 821, "canonical": "unique:amulet", "name": "Highlord's Wrath"},
    {"d2io_id": 826, "canonical": "unique:heirophant_trophy", "name": "Homunculus"},
    {"d2io_id": 834, "canonical": "unique:kraken_shell", "name": "Leviathan"},
    {"d2io_id": 836, "canonical": "unique:grim_shield", "name": "Lidless Wall"},
    {"d2io_id": 839, "canonical": "unique:boneweave_boots", "name": "Marrowwalk"},
    {"d2io_id": 865, "canonical": "unique:spired_helm", "name": "Nightwing's Veil"},
    {"d2io_id": 908, "canonical": "unique:heavy_bracers", "name": "Skin of the Flayed One"},
    {"d2io_id": 922, "canonical": "unique:blade_barrier", "name": "Spike Thorn"},
    {"d2io_id": 926, "canonical": "unique:rune_staff", "name": "Spirit Forge"},
    {"d2io_id": 955, "canonical": "unique:skull_cap", "name": "Tarnhelm"},
    {"d2io_id": 973, "canonical": "unique:colossus_blade", "name": "The Grandfather"},
    {"d2io_id": 982, "canonical": "unique:swirling_crystal", "name": "The Oculus"},
    {"d2io_id": 984, "canonical": "unique:thresher", "name": "The Reaper's Toll"},
    {"d2io_id": 993, "canonical": "unique:matriarchal_javelin", "name": "Thunderstroke"},
    {"d2io_id": 995, "canonical": "unique:ceremonial_javelin", "name": "Titan's Revenge"},
    {"d2io_id": 1021, "canonical": "unique:hydra_bow", "name": "Windforce"},
    # ---- Rainbow Facets ----
    {"d2io_id": 3162, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Fire Die"},
    {"d2io_id": 3160, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Fire Level"},
    {"d2io_id": 3167, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Light Die"},
    {"d2io_id": 3166, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Light Level"},
    {"d2io_id": 3169, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Cold Die"},
    {"d2io_id": 3168, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Cold Level"},
    {"d2io_id": 3165, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Poison Die"},
    {"d2io_id": 3164, "canonical": "jewel:rainbow_facet", "name": "Rainbow Facet Poison Level"},
    # ---- Sunder charms ----
    {"d2io_id": 1135128, "canonical": "charm:sunder", "name": "Flame Rift"},
    {"d2io_id": 1135127, "canonical": "charm:sunder", "name": "Crack of the Heavens"},
    {"d2io_id": 1135124, "canonical": "charm:sunder", "name": "Cold Rupture"},
    {"d2io_id": 1135129, "canonical": "charm:sunder", "name": "Rotting Fissure"},
    {"d2io_id": 1135126, "canonical": "charm:sunder", "name": "Bone Break"},
    {"d2io_id": 1135125, "canonical": "charm:sunder", "name": "Black Cleft"},
    # ---- Unique rings ----
    {"d2io_id": 715, "canonical": "unique:bul_kathos_wedding_band", "name": "BK Wedding Band"},
    {"d2io_id": 884, "canonical": "unique:ring", "name": "Raven Frost"},
    {"d2io_id": 862, "canonical": "unique:ring", "name": "Nagelring"},
    # ---- Additional uniques (auto-generated) ----
    {"d2io_id": 668, "canonical": "unique:sacred_rondache", "name": "Alma Negra"},
    {"d2io_id": 674, "canonical": "unique:tomb_wand", "name": "Arm of King Leoric"},
    {"d2io_id": 677, "canonical": "unique:battle_scythe", "name": "Athena's Wrath"},
    {"d2io_id": 679, "canonical": "unique:embossed_plate", "name": "Atma's Wail"},
    {"d2io_id": 682, "canonical": "unique:knout", "name": "Baezil's Vortex"},
    {"d2io_id": 683, "canonical": "unique:short_staff", "name": "Bane Ash"},
    {"d2io_id": 687, "canonical": "unique:dacian_falx", "name": "Bing Sz Wang"},
    {"d2io_id": 688, "canonical": "unique:chaos_armor", "name": "Black Hades"},
    {"d2io_id": 689, "canonical": "unique:cinquedeas", "name": "Blackbog's Sharp"},
    {"d2io_id": 690, "canonical": "unique:grave_wand", "name": "Blackhand Key"},
    {"d2io_id": 692, "canonical": "unique:bill", "name": "Blackleach Blade"},
    {"d2io_id": 693, "canonical": "unique:luna", "name": "Blackoak Shield"},
    {"d2io_id": 694, "canonical": "unique:bastard_sword", "name": "Blacktongue"},
    {"d2io_id": 696, "canonical": "unique:double_axe", "name": "Bladebone"},
    {"d2io_id": 697, "canonical": "unique:girdle", "name": "Bladebuckle"},
    {"d2io_id": 698, "canonical": "unique:long_war_bow", "name": "Blastbark"},
    {"d2io_id": 700, "canonical": "unique:scimitar", "name": "Blood Crescent"},
    {"d2io_id": 703, "canonical": "unique:gladius", "name": "Bloodletter"},
    {"d2io_id": 704, "canonical": "unique:elegant_blade", "name": "Bloodmoon"},
    {"d2io_id": 1673928, "canonical": "unique:mithril_point", "name": "Bloodpact Shard"},
    {"d2io_id": 705, "canonical": "unique:morning_star", "name": "Bloodrise"},
    {"d2io_id": 706, "canonical": "unique:brandistock", "name": "Bloodthief"},
    {"d2io_id": 707, "canonical": "unique:war_club", "name": "Bloodtree Stump"},
    {"d2io_id": 709, "canonical": "unique:plate_mail", "name": "Boneflesh"},
    {"d2io_id": 712, "canonical": "unique:gothic_axe", "name": "Boneslayer Blade"},
    {"d2io_id": 714, "canonical": "unique:great_axe", "name": "Brainhew"},
    {"d2io_id": 717, "canonical": "unique:cleaver", "name": "Butcher's Pupil"},
    {"d2io_id": 718, "canonical": "unique:tower_shield", "name": "Bverrit Keep"},
    {"d2io_id": 719, "canonical": "unique:petrified_wand", "name": "Carin Shard"},
    {"d2io_id": 723, "canonical": "unique:cedar_staff", "name": "Chromatic Ire"},
    {"d2io_id": 724, "canonical": "unique:long_siege_bow", "name": "Cliffkiller"},
    {"d2io_id": 725, "canonical": "unique:gothic_sword", "name": "Cloudcrack"},
    {"d2io_id": 726, "canonical": "unique:helm", "name": "Coif of Glory"},
    {"d2io_id": 727, "canonical": "unique:hatchet", "name": "Coldkill"},
    {"d2io_id": 728, "canonical": "unique:cutlass", "name": "Coldsteel Eye"},
    {"d2io_id": 729, "canonical": "unique:ornate_armor", "name": "Corpsemourn"},
    {"d2io_id": 730, "canonical": "unique:espadon", "name": "Crainte Vomir"},
    {"d2io_id": 733, "canonical": "unique:tigulated_mail", "name": "Crow Caw"},
    {"d2io_id": 736, "canonical": "unique:mace", "name": "Crushflange"},
    {"d2io_id": 738, "canonical": "unique:cudgel", "name": "Dark Clan Crusher"},
    {"d2io_id": 740, "canonical": "unique:ring_mail", "name": "Darkglow"},
    {"d2io_id": 741, "canonical": "unique:basinet", "name": "Darksight Helm"},
    {"d2io_id": 743, "canonical": "unique:battle_dart", "name": "Deathbit"},
    {"d2io_id": 746, "canonical": "unique:axe", "name": "Deathspade"},
    {"d2io_id": 748, "canonical": "unique:chu_ko_nu", "name": "Demon Machine"},
    {"d2io_id": 749, "canonical": "unique:destroyer_helm", "name": "Demonhorn's Edge"},
    {"d2io_id": 750, "canonical": "unique:balrog_spear", "name": "Demon's Arch"},
    {"d2io_id": 756, "canonical": "unique:zakarum_shield", "name": "Dragonscale"},
    {"d2io_id": 758, "canonical": "unique:full_helm", "name": "Duskdeep"},
    {"d2io_id": 760, "canonical": "unique:crusader_bow", "name": "Eaglehorn"},
    {"d2io_id": 762, "canonical": "unique:battle_hammer", "name": "Earthshaker"},
    {"d2io_id": 763, "canonical": "unique:double_bow", "name": "Endlesshail"},
    {"d2io_id": 765, "canonical": "unique:silver_edged_axe", "name": "Ethereal Edge"},
    {"d2io_id": 766, "canonical": "unique:glorious_axe", "name": "Executioner's Justice"},
    {"d2io_id": 767, "canonical": "unique:club", "name": "Felloak"},
    {"d2io_id": 769, "canonical": "unique:balrog_blade", "name": "Flamebellow"},
    {"d2io_id": 770, "canonical": "unique:barbed_club", "name": "Fleshrender"},
    {"d2io_id": 771, "canonical": "unique:fanged_knife", "name": "Fleshripper"},
    {"d2io_id": 773, "canonical": "unique:cryptic_sword", "name": "Frostwind"},
    {"d2io_id": 774, "canonical": "unique:winged_harpoon", "name": "Gargoyle's Bite"},
    {"d2io_id": 777, "canonical": "unique:legend_spike", "name": "Ghostflame"},
    {"d2io_id": 780, "canonical": "unique:flying_axe", "name": "Gimmershred"},
    {"d2io_id": 781, "canonical": "unique:dimensional_blade", "name": "Ginther's Rift"},
    {"d2io_id": 782, "canonical": "unique:falchion", "name": "Gleamscythe"},
    {"d2io_id": 785, "canonical": "unique:full_plate_mail", "name": "Goldskin"},
    {"d2io_id": 789, "canonical": "unique:heavy_boots", "name": "Gorefoot"},
    {"d2io_id": 790, "canonical": "unique:broad_axe", "name": "Goreshovel"},
    {"d2io_id": 791, "canonical": "unique:bone_wand", "name": "Gravenspine"},
    {"d2io_id": 792, "canonical": "unique:sharkskin_gloves", "name": "Gravepalm"},
    {"d2io_id": 793, "canonical": "unique:quilted_armor", "name": "Greyform"},
    {"d2io_id": 795, "canonical": "unique:grim_scythe", "name": "Grim's Burning Dead"},
    {"d2io_id": 798, "canonical": "unique:naga", "name": "Guardian Naga"},
    {"d2io_id": 799, "canonical": "unique:dagger", "name": "Gull"},
    {"d2io_id": 801, "canonical": "unique:conqueror_crown", "name": "Halaberd's Reign"},
    {"d2io_id": 802, "canonical": "unique:divine_scepter", "name": "Hand of Blessed Light"},
    {"d2io_id": 803, "canonical": "unique:scale_mail", "name": "Hawkmail"},
    {"d2io_id": 805, "canonical": "unique:battle_sword", "name": "Headstriker"},
    {"d2io_id": 806, "canonical": "unique:rondel", "name": "Heart Carver"},
    {"d2io_id": 807, "canonical": "unique:light_plate", "name": "Heavenly Garb"},
    {"d2io_id": 809, "canonical": "unique:heavy_crossbow", "name": "Hellcast"},
    {"d2io_id": 810, "canonical": "unique:short_war_bow", "name": "Hellclap"},
    {"d2io_id": 812, "canonical": "unique:long_sword", "name": "Hellplague"},
    {"d2io_id": 813, "canonical": "unique:colossus_crossbow", "name": "Hellrack"},
    {"d2io_id": 816, "canonical": "unique:shamshir", "name": "Hexfire"},
    {"d2io_id": 818, "canonical": "unique:heirophant_trophy", "name": "Homunculus"},
    {"d2io_id": 819, "canonical": "unique:yari", "name": "Hone Sundan"},
    {"d2io_id": 821, "canonical": "unique:leather_boots", "name": "Hotspur"},
    {"d2io_id": 822, "canonical": "unique:great_helm", "name": "Howltusk"},
    {"d2io_id": 824, "canonical": "unique:bec_de_corbin", "name": "Husoldal Evo"},
    {"d2io_id": 825, "canonical": "unique:splint_mail", "name": "Iceblink"},
    {"d2io_id": 826, "canonical": "unique:crossbow", "name": "Ichorsting"},
    {"d2io_id": 827, "canonical": "unique:demonhide_boots", "name": "Infernostride"},
    {"d2io_id": 829, "canonical": "unique:war_hammer", "name": "Ironstone"},
    {"d2io_id": 830, "canonical": "unique:twin_axe", "name": "Islestrike"},
    {"d2io_id": 833, "canonical": "unique:fuscina", "name": "Kelpie Snare"},
    {"d2io_id": 836, "canonical": "unique:scepter", "name": "Knell Striker"},
    {"d2io_id": 837, "canonical": "unique:cedarbow", "name": "Kuko Shakaku"},
    {"d2io_id": 838, "canonical": "unique:winged_axe", "name": "Lacerator"},
    {"d2io_id": 839, "canonical": "unique:barbed_shield", "name": "Lance Guard"},
    {"d2io_id": 840, "canonical": "unique:spetum", "name": "Lance of Yaggai"},
    {"d2io_id": 841, "canonical": "unique:arbalest", "name": "Langer Briser"},
    {"d2io_id": 843, "canonical": "unique:light_crossbow", "name": "Leadcrow"},
    {"d2io_id": 848, "canonical": "unique:ceremonial_bow", "name": "Lycander's Aim"},
    {"d2io_id": 849, "canonical": "unique:ceremonial_pike", "name": "Lycander's Flank"},
    {"d2io_id": 852, "canonical": "unique:rune_bow", "name": "Magewrath"},
    {"d2io_id": 857, "canonical": "unique:aegis", "name": "Medusa's Gaze"},
    {"d2io_id": 860, "canonical": "unique:jagged_star", "name": "Moonfall"},
    {"d2io_id": 864, "canonical": "unique:belt", "name": "Nightsmoke"},
    {"d2io_id": 872, "canonical": "unique:buckler", "name": "Pelta Lunata"},
    {"d2io_id": 874, "canonical": "unique:rune_sword", "name": "Plague Bearer"},
    {"d2io_id": 875, "canonical": "unique:short_bow", "name": "Pluckeye"},
    {"d2io_id": 881, "canonical": "unique:war_axe", "name": "Rakescar"},
    {"d2io_id": 882, "canonical": "unique:gothic_plate", "name": "Rattlecage"},
    {"d2io_id": 885, "canonical": "unique:sky_spirit", "name": "Ravenlore"},
    {"d2io_id": 888, "canonical": "unique:trident", "name": "Razortine"},
    {"d2io_id": 890, "canonical": "unique:razor_bow", "name": "Riphook"},
    {"d2io_id": 891, "canonical": "unique:flamberge", "name": "Ripsaw"},
    {"d2io_id": 893, "canonical": "unique:field_plate", "name": "Rockfleece"},
    {"d2io_id": 894, "canonical": "unique:sallet", "name": "Rockstopper"},
    {"d2io_id": 897, "canonical": "unique:grand_scepter", "name": "Rusthandle"},
    {"d2io_id": 901, "canonical": "unique:long_staff", "name": "Serpent Lord"},
    {"d2io_id": 904, "canonical": "unique:2_handed_sword", "name": "Shadowfang"},
    {"d2io_id": 913, "canonical": "unique:edge_bow", "name": "Skystrike"},
    {"d2io_id": 914, "canonical": "unique:light_belt", "name": "Snakecord"},
    {"d2io_id": 918, "canonical": "unique:claymore", "name": "Soulflay"},
    {"d2io_id": 919, "canonical": "unique:chain_mail", "name": "Sparking Mail"},
    {"d2io_id": 921, "canonical": "unique:bearded_axe", "name": "Spellsteel"},
    {"d2io_id": 923, "canonical": "unique:poignard", "name": "Spineripper"},
    {"d2io_id": 924, "canonical": "unique:lance", "name": "Spire of Honor"},
    {"d2io_id": 928, "canonical": "unique:ward", "name": "Spirit Ward"},
    {"d2io_id": 933, "canonical": "unique:kite_shield", "name": "Steelclash"},
    {"d2io_id": 934, "canonical": "unique:great_maul", "name": "Steeldriver"},
    {"d2io_id": 935, "canonical": "unique:voulge", "name": "Steelgoad"},
    {"d2io_id": 936, "canonical": "unique:ogre_gauntlets", "name": "Steelrend"},
    {"d2io_id": 939, "canonical": "unique:matriarchal_spear", "name": "Stoneraven"},
    {"d2io_id": 940, "canonical": "unique:scutum", "name": "Stormchaser"},
    {"d2io_id": 941, "canonical": "unique:war_scepter", "name": "Stormeye"},
    {"d2io_id": 942, "canonical": "unique:large_shield", "name": "Stormguild"},
    {"d2io_id": 944, "canonical": "unique:tabar", "name": "Stormrider"},
    {"d2io_id": 946, "canonical": "unique:stilleto", "name": "Stormspike"},
    {"d2io_id": 949, "canonical": "unique:spiked_club", "name": "Stoutnail"},
    {"d2io_id": 951, "canonical": "unique:burnt_wand", "name": "Suicide Branch"},
    {"d2io_id": 952, "canonical": "unique:flanged_mace", "name": "Sureshrill Frost"},
    {"d2io_id": 953, "canonical": "unique:spiked_shield", "name": "Swordback Hold"},
    {"d2io_id": 954, "canonical": "unique:executioner_sword", "name": "Swordguard"},
    {"d2io_id": 956, "canonical": "unique:plate_boots", "name": "Tearhaunch"},
    {"d2io_id": 957, "canonical": "unique:sacred_armor", "name": "Templar's Might"},
    {"d2io_id": 959, "canonical": "unique:poleaxe", "name": "The Battlebranch"},
    {"d2io_id": 961, "canonical": "unique:hard_leather", "name": "The Centurion"},
    {"d2io_id": 964, "canonical": "unique:dirk", "name": "The Diggler"},
    {"d2io_id": 965, "canonical": "unique:spear", "name": "The Dragon Chang"},
    {"d2io_id": 967, "canonical": "unique:mask", "name": "The Face of Horror"},
    {"d2io_id": 968, "canonical": "unique:holy_water_sprinkler", "name": "The Fetid Sprinkler"},
    {"d2io_id": 969, "canonical": "unique:martel_de_fer", "name": "The Gavel of Pain"},
    {"d2io_id": 972, "canonical": "unique:hand_axe", "name": "The Gnasher"},
    {"d2io_id": 974, "canonical": "unique:war_scythe", "name": "The Grim Reaper"},
    {"d2io_id": 975, "canonical": "unique:gloves", "name": "The Hand of Broc"},
    {"d2io_id": 976, "canonical": "unique:war_spear", "name": "The Impaler"},
    {"d2io_id": 977, "canonical": "unique:war_staff", "name": "The Iron Jang Bong"},
    {"d2io_id": 980, "canonical": "unique:lochaber_axe", "name": "The Meat Scraper"},
    {"d2io_id": 983, "canonical": "unique:great_sword", "name": "The Patriarch"},
    {"d2io_id": 987, "canonical": "unique:battle_staff", "name": "The Salamander"},
    {"d2io_id": 988, "canonical": "unique:francisca", "name": "The Scalper"},
    {"d2io_id": 989, "canonical": "unique:ghost_armor", "name": "The Spirit Shroud"},
    {"d2io_id": 991, "canonical": "unique:tusk_sword", "name": "The Vile Husk"},
    {"d2io_id": 992, "canonical": "unique:gothic_shield", "name": "The Ward"},
    {"d2io_id": 994, "canonical": "unique:dragon_shield", "name": "Tiamat's Rebuke"},
    {"d2io_id": 996, "canonical": "unique:zweihander", "name": "Todesfaelle Flamme"},
    {"d2io_id": 998, "canonical": "unique:sharktooth_armor", "name": "Toothrow"},
    {"d2io_id": 1000, "canonical": "unique:chain_boots", "name": "Treads of Cthon"},
    {"d2io_id": 1003, "canonical": "unique:small_shield", "name": "Umbral Disk"},
    {"d2io_id": 1005, "canonical": "unique:crown", "name": "Undead Crown"},
    {"d2io_id": 1009, "canonical": "unique:demonhide_gloves", "name": "Venom Grip"},
    {"d2io_id": 1012, "canonical": "unique:war_fork", "name": "Viperfork"},
    {"d2io_id": 1013, "canonical": "unique:defender", "name": "Visceratuant"},
    {"d2io_id": 1017, "canonical": "unique:gothic_staff", "name": "Warpspear"},
    {"d2io_id": 1018, "canonical": "unique:winged_knife", "name": "Warshrike"},
    {"d2io_id": 1025, "canonical": "unique:hunter_92s_bow", "name": "Witherstring"},
    {"d2io_id": 1027, "canonical": "unique:long_battle_bow", "name": "Wizendraw"},
    {"d2io_id": 1028, "canonical": "unique:halberd", "name": "Woestave"},
    {"d2io_id": 1030, "canonical": "unique:bone_helm", "name": "Wormskull"},
    {"d2io_id": 1032, "canonical": "unique:rune_scepter", "name": "Zakarum's Hand"},
    {"d2io_id": 1673925, "canonical": "unique:burnt_text", "name": "Measured Wrath"},
    {"d2io_id": 1673926, "canonical": "unique:legend_sword", "name": "Dreadfang"},
    {"d2io_id": 1673927, "canonical": "unique:mirrored_boots", "name": "Wraithstep"},
    {"d2io_id": 1673928, "canonical": "unique:mithril_point", "name": "Bloodpact Shard"},
    {"d2io_id": 1674266, "canonical": "unique:jewel", "name": "Guardian's Light"},
    {"d2io_id": 4, "canonical": "set:mask", "name": "Cathan's Visage"},
    {"d2io_id": 30, "canonical": "set:battle_staff", "name": "Cathan's Rule"},
    {"d2io_id": 33, "canonical": "set:chain_mail", "name": "Cathan's Mesh"},
    {"d2io_id": 59, "canonical": "set:war_belt", "name": "Immortal King's Detail"},
    {"d2io_id": 1035, "canonical": "set:hunters_guise", "name": "Aldur's Stony Gaze"},
    {"d2io_id": 1036, "canonical": "set:shadow_plate", "name": "Aldur's Deception"},
    {"d2io_id": 1037, "canonical": "set:battle_boots", "name": "Aldur's Advance"},
    {"d2io_id": 1040, "canonical": "set:ring", "name": "Angelic Halo"},
    {"d2io_id": 1041, "canonical": "set:ring_mail", "name": "Angelic Mantle"},
    {"d2io_id": 1042, "canonical": "set:sabre", "name": "Angelic Sickle"},
    {"d2io_id": 1045, "canonical": "set:skull_cap", "name": "Arcanna's Head"},
    {"d2io_id": 1046, "canonical": "set:light_plate", "name": "Arcanna's Flesh"},
    {"d2io_id": 1047, "canonical": "set:war_staff", "name": "Arcanna's Deathwand"},
    {"d2io_id": 1049, "canonical": "set:light_gauntlets", "name": "Arctic Mitts"},
    {"d2io_id": 1051, "canonical": "set:quilted_armor", "name": "Arctic Furs"},
    {"d2io_id": 1052, "canonical": "set:short_war_bow", "name": "Arctic Horn"},
    {"d2io_id": 1054, "canonical": "set:double_axe", "name": "Berserker's Hatchet"},
    {"d2io_id": 1055, "canonical": "set:splint_mail", "name": "Berserker's Hauberk"},
    {"d2io_id": 1056, "canonical": "set:helm", "name": "Berserker's Headgear"},
    {"d2io_id": 1061, "canonical": "set:grand_scepter", "name": "Civerb's Cudgel"},
    {"d2io_id": 1062, "canonical": "set:large_shield", "name": "Civerb's Ward"},
    {"d2io_id": 1066, "canonical": "set:small_shield", "name": "Cleglaw's Claw"},
    {"d2io_id": 1067, "canonical": "set:chain_gloves", "name": "Cleglaw's Pincers"},
    {"d2io_id": 1069, "canonical": "set:war_hat", "name": "Cow King's Horns"},
    {"d2io_id": 1070, "canonical": "set:studded_leather", "name": "Cow King's Hide"},
    {"d2io_id": 1074, "canonical": "set:sash", "name": "Death's Guard"},
    {"d2io_id": 1075, "canonical": "set:leather_gloves", "name": "Death's Hand"},
    {"d2io_id": 1078, "canonical": "set:corona", "name": "Griswold's Valor"},
    {"d2io_id": 1080, "canonical": "set:vortex_shield", "name": "Griswold's Honor"},
    {"d2io_id": 1085, "canonical": "set:spired_helm", "name": "Ondal's Almighty"},
    {"d2io_id": 1091, "canonical": "set:bill", "name": "Hwanin's Justice"},
    {"d2io_id": 1092, "canonical": "set:tigulated_mail", "name": "Hwanin's Refuge"},
    {"d2io_id": 1093, "canonical": "set:grand_crown", "name": "Hwanin's Splendor"},
    {"d2io_id": 1095, "canonical": "set:avenger_guard", "name": "Immortal King's Will"},
    {"d2io_id": 1097, "canonical": "set:war_gauntlets", "name": "Immortal King's Forge"},
    {"d2io_id": 1098, "canonical": "set:war_boots", "name": "Immortal King's Pillar"},
    {"d2io_id": 1100, "canonical": "set:heavy_belt", "name": "Infernal Sign"},
    {"d2io_id": 1109, "canonical": "set:broad_sword", "name": "Isenhart's Lightbrand"},
    {"d2io_id": 1110, "canonical": "set:breast_plate", "name": "Isenhart's Case"},
    {"d2io_id": 1111, "canonical": "set:full_helm", "name": "Isenhart's Horns"},
    {"d2io_id": 1112, "canonical": "set:gothic_shield", "name": "Isenhart's Parry"},
    {"d2io_id": 1120, "canonical": "set:war_scepter", "name": "Milabrega's Rod"},
    {"d2io_id": 1121, "canonical": "set:ancient_armor", "name": "Milabrega's Robe"},
    {"d2io_id": 1122, "canonical": "set:crown", "name": "Milabrega's Diadem"},
    {"d2io_id": 1123, "canonical": "set:kite_shield", "name": "Milabrega's Orb"},
    {"d2io_id": 1125, "canonical": "set:circlet", "name": "Naj's Circlet"},
    {"d2io_id": 1126, "canonical": "set:hellforge_plate", "name": "Naj's Light Plate"},
    {"d2io_id": 1127, "canonical": "set:elder_staff", "name": "Naj's Puzzler"},
    {"d2io_id": 1129, "canonical": "set:scissors_suwayyah", "name": "Natalya's Mark"},
    {"d2io_id": 1130, "canonical": "set:loricated_mail", "name": "Natalya's Shadow"},
    {"d2io_id": 1132, "canonical": "set:mesh_boots", "name": "Natalya's Soul"},
    {"d2io_id": 1136, "canonical": "set:battle_belt", "name": "Wilhelm's Pride"},
    {"d2io_id": 1143, "canonical": "set:cryptic_sword", "name": "Sazabi's Cobalt Redeemer"},
    {"d2io_id": 1144, "canonical": "set:balrog_skin", "name": "Sazabi's Ghost Liberator"},
    {"d2io_id": 1145, "canonical": "set:basinet", "name": "Sazabi's Mental Sheath"},
    {"d2io_id": 1147, "canonical": "set:gothic_plate", "name": "Sigon's Shelter"},
    {"d2io_id": 1149, "canonical": "set:tower_shield", "name": "Sigon's Guard"},
    {"d2io_id": 1160, "canonical": "set:bone_helm", "name": "Tancred's Skull"},
    {"d2io_id": 1162, "canonical": "set:boots", "name": "Tancred's Hobnails"},
    {"d2io_id": 1164, "canonical": "set:military_pick", "name": "Tancred's Crowbill"},
    {"d2io_id": 1167, "canonical": "set:mithril_coil", "name": "Credendum"},
    {"d2io_id": 1169, "canonical": "set:demonhide_boots", "name": "Rite of Passage"},
    {"d2io_id": 1170, "canonical": "set:amulet", "name": "Telling of Beads"},
    {"d2io_id": 1179, "canonical": "set:leather_armor", "name": "Vidala's Ambush"},
    {"d2io_id": 1180, "canonical": "set:light_plated_boots", "name": "Vidala's Fetlock"},
    {"d2io_id": 1181, "canonical": "set:long_battle_bow", "name": "Vidala's Barb"},
    {"d2io_id": 1673915, "canonical": "set:hard_leather_armor", "name": "Bane's Wraithskin"},
    {"d2io_id": 1673916, "canonical": "set:light_belt", "name": "Bane's Authority"},
    {"d2io_id": 1673917, "canonical": "set:demonhead", "name": "Horazon's Countenance"},
    {"d2io_id": 1673918, "canonical": "set:russet_armor", "name": "Horazon's Dominion"},
    {"d2io_id": 1673919, "canonical": "set:demonhide_gloves", "name": "Horazon's Hold"},
    {"d2io_id": 1673920, "canonical": "set:mirrored_boots", "name": "Horazon's Legacy"},
    {"d2io_id": 1673921, "canonical": "set:occult_codex", "name": "Horazon's Secrets"},
    {"d2io_id": 1674031, "canonical": "set:kriss", "name": "Bane's Oathmaker"},
]

# (Extended list removed — all items are in D2IO_ITEMS now)

# Rune name -> rune code for fg conversion
RUNE_NAMES = {
    "el": "r01", "eld": "r02", "tir": "r03", "nef": "r04", "eth": "r05",
    "ith": "r06", "tal": "r07", "ral": "r08", "ort": "r09", "thul": "r10",
    "amn": "r11", "sol": "r12", "shael": "r13", "dol": "r14", "hel": "r15",
    "io": "r16", "lum": "r17", "ko": "r18", "fal": "r19", "lem": "r20",
    "pul": "r21", "um": "r22", "mal": "r23", "ist": "r24", "gul": "r25",
    "vex": "r26", "ohm": "r27", "lo": "r28", "sur": "r29", "ber": "r30",
    "jah": "r31", "cham": "r32", "zod": "r33",
}


def _load_rune_fg_rates(conn: sqlite3.Connection, market_key: str) -> dict[str, float]:
    """Load rune name -> fg rate from price_estimates."""
    rates: dict[str, float] = {}
    rows = conn.execute(
        "SELECT variant_key, estimate_fg FROM price_estimates WHERE market_key = ? AND variant_key LIKE 'rune:%'",
        (market_key,),
    ).fetchall()
    for r in rows:
        vk = r[0]  # e.g. "rune:jah"
        rune_name = vk.split(":")[-1]
        rates[rune_name] = r[1]
    return rates


def _fetch_pricecheck_page(item_id: int) -> str | None:
    """Fetch a diablo2.io pricecheck page. Returns HTML text or None on error."""
    url = f"https://diablo2.io/pricecheck.php?item={item_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) d2lut-price-tool/1.0",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  WARN: fetch failed for item {item_id}: {e}")
        return None


# Regex patterns for extracting rune payments from diablo2.io trade listings
# Trades show patterns like "For 1 Ist", "For 1 Mal 15 Perfect Gems", etc.
_RUNE_PAYMENT_RE = re.compile(
    r"(?:^|\s)(\d+)\s+"
    r"(?:\[([A-Z][a-z]+(?:\s+Rune)?)\]"  # linked rune like [Ist]
    r"|([A-Z][a-z]+)\s*(?:Rune)?)"        # plain rune name
    , re.IGNORECASE
)

# Simpler: look for rune names in "For X RuneName" patterns
_TRADE_LINE_RE = re.compile(
    r"for\s+"
    r"(?:(\d+)\s+)?"
    r"(El|Eld|Tir|Nef|Eth|Ith|Tal|Ral|Ort|Thul|Amn|Sol|Shael|Dol|Hel|Io|Lum|Ko|Fal|Lem|Pul|Um|Mal|Ist|Gul|Vex|Ohm|Lo|Sur|Ber|Jah|Cham|Zod)"
    r"(?:\s|$|[,\.])",
    re.IGNORECASE,
)

# Perfect gems pattern (used as currency, ~2-3fg each)
_PGEM_RE = re.compile(r"(\d+)\s+(?:Perfect\s+Gems?|[Pp]gems?|pgems?)", re.IGNORECASE)

# Time ago pattern
_TIME_AGO_RE = re.compile(r"(\d+)\s+(day|week|month|hour|minute)s?\s+ago", re.IGNORECASE)


def _parse_trades_from_html(html: str, rune_rates: dict[str, float]) -> list[dict]:
    """Parse trade listings from diablo2.io pricecheck raw HTML.

    Each trade is in a <li class="z-pc-li"> block.
    Rune payments appear as links like misc/ist-t52.html preceded by a quantity span.
    Time info is in z-relative-date spans.

    Returns list of {fg_price, rune_payment, time_ago_str, raw_excerpt}.
    """
    trades: list[dict] = []

    # Split into individual trade listing blocks
    blocks = html.split('class="z-pc-li"')
    if len(blocks) < 2:
        return trades

    # Rune link pattern: <span class="z-blue">N</span> ... misc/runename-tNN.html
    rune_link_re = re.compile(
        r'<span class="z-blue">(\d+)</span>\s*'
        r'<span class="ajax_catch"><a[^>]*href="misc/([a-z]+)-t\d+\.html"',
        re.IGNORECASE,
    )
    # Also match single rune without explicit quantity (qty=1 implied)
    rune_link_single_re = re.compile(
        r'For\s*\n?\s*<span class="z-blue">(\d+)</span>\s*'
        r'<span class="ajax_catch"><a[^>]*href="misc/([a-z]+)-t\d+\.html"',
        re.IGNORECASE,
    )
    # Perfect gems pattern
    pgem_link_re = re.compile(
        r'<span class="z-blue">(\d+)</span>\s*'
        r'<span class="ajax_catch"><a[^>]*href="misc/perfect-gems-t\d+\.html"',
        re.IGNORECASE,
    )
    # Time pattern from title attribute
    time_re = re.compile(r'title="([^"]*\d{4}[^"]*)"[^>]*class="z-relative-date"', re.IGNORECASE)
    time_re2 = re.compile(r'class="z-relative-date"[^>]*title="([^"]*\d{4}[^"]*)"', re.IGNORECASE)
    # Seller pattern
    seller_re = re.compile(r'Seller:.*?href="/member/([^"]+)"', re.IGNORECASE)
    # Buyer pattern (indicates completed trade)
    buyer_re = re.compile(r'Buyer:?\s*.*?href="/member/([^"]+)"', re.IGNORECASE | re.DOTALL)
    # Ladder/season pattern
    season_re = re.compile(r'title="Ladder Season (\d+)"', re.IGNORECASE)
    # Description
    desc_re = re.compile(r'class="z-price-desc"[^>]*>.*?<span>(.*?)</span>', re.IGNORECASE | re.DOTALL)

    for block in blocks[1:]:  # skip first (before first listing)
        # Extract all rune payments in this block
        rune_matches = rune_link_re.findall(block)
        pgem_matches = pgem_link_re.findall(block)

        # Check if this is a completed trade (has buyer)
        has_buyer = bool(buyer_re.search(block))

        # Extract time
        time_match = time_re.search(block) or time_re2.search(block)
        time_str = time_match.group(1) if time_match else ""

        # Extract season
        season_match = season_re.search(block)
        season = int(season_match.group(1)) if season_match else 0

        # Calculate total fg from rune payments
        total_fg = 0.0
        payment_parts: list[str] = []

        for qty_str, rune_name in rune_matches:
            rune_name_lower = rune_name.lower()
            # Skip if this is "perfect-gems" (handled separately)
            if rune_name_lower in ("perfect", "gems"):
                continue
            qty = int(qty_str) if qty_str else 1
            if rune_name_lower in rune_rates:
                total_fg += rune_rates[rune_name_lower] * qty
                payment_parts.append(f"{qty}x {rune_name_lower}")

        for qty_str in pgem_matches:
            qty = int(qty_str) if qty_str else 1
            total_fg += qty * 2.5  # pgems ~2.5fg each
            payment_parts.append(f"{qty}x pgems")

        if total_fg > 0 and payment_parts:
            # Only include completed trades (has buyer) or recent listings
            # Prefer completed trades for accuracy
            trades.append({
                "fg_price": round(total_fg, 1),
                "rune_payment": " + ".join(payment_parts),
                "time_ago_str": time_str,
                "raw_excerpt": f"completed={has_buyer} season={season}",
                "has_buyer": has_buyer,
                "season": season,
            })

    return trades


def _insert_observed_prices(
    conn: sqlite3.Connection,
    canonical_item_id: str,
    trades: list[dict],
    market_key: str,
    d2io_id: int,
    item_name: str,
    dry_run: bool = False,
) -> int:
    """Insert parsed trades as observed_prices rows. Returns count inserted."""
    now_iso = datetime.now(timezone.utc).isoformat()
    source_url = f"https://diablo2.io/pricecheck.php?item={d2io_id}"
    inserted = 0

    for t in trades:
        if t["fg_price"] <= 0:
            continue
        if dry_run:
            print(f"    DRY-RUN: {canonical_item_id} = {t['fg_price']}fg ({t['rune_payment']}) [{t['time_ago_str']}]")
            inserted += 1
            continue

        conn.execute(
            """INSERT INTO observed_prices
               (source, market_key, forum_id, thread_id, post_id, source_kind,
                signal_kind, canonical_item_id, variant_key, price_fg, confidence,
                observed_at, source_url, raw_excerpt, thread_trade_type, thread_category_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "diablo2.io",
                market_key,
                0,  # forum_id
                d2io_id,  # thread_id (use d2io item id)
                0,  # post_id
                "pricecheck",  # source_kind
                "SOLD",  # signal_kind (completed trades)
                canonical_item_id,
                canonical_item_id,  # variant_key = canonical for now
                t["fg_price"],
                0.7,  # confidence (external source, rune-converted)
                now_iso,
                source_url,
                f"[diablo2.io] {item_name}: {t['rune_payment']} | {t['raw_excerpt'][:100]}",
                "FT",  # thread_trade_type
                0,  # thread_category_id
            ),
        )
        inserted += 1

    return inserted


def main() -> int:
    p = argparse.ArgumentParser(description="Scrape diablo2.io prices")
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--market-key", default="d2r_sc_ladder")
    p.add_argument("--dry-run", action="store_true", help="Parse but don't insert")
    p.add_argument("--delay", type=float, default=2.0, help="Delay between requests (seconds)")
    p.add_argument("--limit", type=int, default=0, help="Max items to fetch (0=all)")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Load rune->fg rates
    rune_rates = _load_rune_fg_rates(conn, args.market_key)
    if not rune_rates:
        print("ERROR: No rune rates found in price_estimates")
        return 2
    print(f"Loaded {len(rune_rates)} rune->fg rates")
    for rn in ("ist", "mal", "um", "pul", "vex", "ohm", "lo", "ber", "jah"):
        if rn in rune_rates:
            print(f"  {rn}: {rune_rates[rn]}fg")

    items = list(D2IO_ITEMS)

    if args.limit > 0:
        items = items[:args.limit]

    total_inserted = 0
    total_trades = 0

    for idx, item in enumerate(items):
        d2io_id = item["d2io_id"]
        canonical = item["canonical"]
        name = item["name"]

        print(f"\n[{idx+1}/{len(items)}] Fetching {name} (d2io={d2io_id}, canonical={canonical})...")

        html = _fetch_pricecheck_page(d2io_id)
        if not html:
            continue

        trades = _parse_trades_from_html(html, rune_rates)
        total_trades += len(trades)

        if trades:
            # Take up to 30 most recent trades
            trades = trades[:30]
            n = _insert_observed_prices(
                conn, canonical, trades, args.market_key, d2io_id, name, args.dry_run
            )
            total_inserted += n
            print(f"  Found {len(trades)} trades, inserted {n}")
            # Show price summary
            prices = [t["fg_price"] for t in trades]
            if prices:
                prices.sort()
                median = prices[len(prices) // 2]
                print(f"  Price range: {min(prices):.0f} - {max(prices):.0f}fg, median: {median:.0f}fg")
        else:
            print(f"  No parseable trades found")

        if idx < len(items) - 1:
            time.sleep(args.delay)

    if not args.dry_run:
        conn.commit()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {total_trades} trades parsed, {total_inserted} inserted")
    print(f"{'='*60}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
