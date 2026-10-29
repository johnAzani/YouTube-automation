"""Autonomous Multi-Language Metadata Localizer.

Generates verified Spanish (es) and Portuguese (pt) metadata localizations
for YouTube video uploads, unlocking global Latin American and Brazilian
audiences under the $0.00 hard cost lock (0 extra API quota units).
"""
from __future__ import annotations

from typing import Any

# Canonical biblical translations for core scripture liturgies
LOCALIZATION_DICTIONARY: dict[str, dict[str, dict[str, str]]] = {
    "psalm 91": {
        "es": {
            "title": "Salmo 91: La Oración Completa de Protección Divina Antes de Dormir | The Secret Place",
            "hook": "El que habita al abrigo del Altísimo morará bajo la sombra del Omnipotente. Diré yo de Jehová: Esperanza mía, y castillo mío; Mi Dios, en quien confiaré.",
        },
        "pt": {
            "title": "Salmo 91: A Oração Completa de Proteção Divina Antes de Dormir | The Secret Place",
            "hook": "Aquele que habita no esconderijo do Altíssimo, à sombra do Onipotente descansará. Direi do Senhor: Ele é o meu Deus, o meu refúgio, a minha fortaleza, e nele confiarei.",
        },
    },
    "psalm 23": {
        "es": {
            "title": "Salmo 23: El Señor Es Mi Pastor — Oración Nocturna para Paz y Descanso | The Secret Place",
            "hook": "Jehová es mi pastor; nada me faltará. En lugares de delicados pastos me hará descansar; Junto a aguas de reposo me pastoreará. Confortará mi alma.",
        },
        "pt": {
            "title": "Salmo 23: O Senhor É Meu Pastor — Oração da Noite para Paz e Descanso | The Secret Place",
            "hook": "O Senhor é o meu pastor, nada me faltará. Deitar-me faz em verdes pastos, guia-me mansamente a águas tranqüilas. Refrigera a minha alma.",
        },
    },
    "psalm 121": {
        "es": {
            "title": "Salmo 121: El Que Te Guarda No Dormirá — Oración de Protección Antes de Dormir",
            "hook": "Alzaré mis ojos a los montes; ¿De dónde vendrá mi socorro? Mi socorro viene de Jehová, Que hizo los cielos y la tierra. No dará tu pie al resbaladero, Ni se dormirá el que te guarda.",
        },
        "pt": {
            "title": "Salmo 121: Aquele Que Te Guarda Não Dormirá — Oração da Noite e Proteção",
            "hook": "Levantarei os meus olhos para os montes, de onde vem o meu socorro. O meu socorro vem do Senhor que fez o céu e a terra. Não deixará vacilar o teu pé; aquele que te guarda não tosquenejará.",
        },
    },
    "psalm 27": {
        "es": {
            "title": "Salmo 27: El Señor Es Mi Luz y Mi Salvación — No Temas al Mal Antes de Dormir",
            "hook": "Jehová es mi luz y mi salvación; ¿de quién temeré? Jehová es la fortaleza de mi vida; ¿de quién he de atemorizarme?",
        },
        "pt": {
            "title": "Salmo 27: O Senhor É Minha Luz e Minha Salvação — Não Temas O Mal",
            "hook": "O Senhor é a minha luz e a minha salvação; a quem temerei? O Senhor é a força da minha vida; de quem me recearei?",
        },
    },
}


def build_metadata_localizations(
    title: str,
    description: str,
    niche: str = "faith and prayer",
) -> dict[str, dict[str, str]]:
    """Build localized title and description dictionary for YouTube Data API v3."""
    title_lower = title.lower()
    matched_key = None

    for key in LOCALIZATION_DICTIONARY:
        if key in title_lower:
            matched_key = key
            break

    if not matched_key:
        # Default Spanish and Portuguese fallbacks for general bedtime prayers
        return {
            "es": {
                "title": f"Oración de la Noche para Dormir en Paz | The Secret Place"[:95],
                "description": (
                    "Oración nocturna de protección divina y paz. Descansa bajo la sombra del Altísimo.\n\n"
                    + description[:4500]
                )[:4900],
            },
            "pt": {
                "title": f"Oração da Noite para Dormir em Paz | The Secret Place"[:95],
                "description": (
                    "Oração poderosa da noite para proteção e paz espiritual. Descanse sob as asas de Deus.\n\n"
                    + description[:4500]
                )[:4900],
            },
        }

    loc_data = LOCALIZATION_DICTIONARY[matched_key]
    localizations = {}

    for lang_code, trans in loc_data.items():
        loc_title = trans["title"][:95]
        loc_desc = (
            f"{trans['hook']}\n\n"
            f"Escucha esta poderosa oración antes de dormir para recibir la paz de Dios y protección sobre tu hogar.\n\n"
            f"{description[:4000]}"
        )[:4900]
        localizations[lang_code] = {
            "title": loc_title,
            "description": loc_desc,
        }

    return localizations
