"""Autonomous Multi-Language Metadata Localizer.

Generates verified Spanish (es) and Portuguese (pt) metadata localizations
for YouTube video uploads, unlocking global Hispanic, Lusophone African, and
Brazilian audiences under the $0.00 hard cost lock (0 extra API quota units).
"""
from __future__ import annotations

import re

from .metadata import smart_truncate_title, truncate_utf8_bytes
from .social_pack import SELAR_JOURNAL_URL, SELAR_STORE_URL

# Canonical biblical translations (Reina-Valera 1909 & Almeida Public Domain)
LOCALIZATION_DICTIONARY: dict[str, dict[str, dict[str, str]]] = {
    "psalm 91": {
        "es": {
            "title": "Salmo 91 Oración de la Noche para Dormir en Paz y Protección",
            "hook": "El que habita al abrigo del Altísimo morará bajo la sombra del Omnipotente. Diré yo de Jehová: Esperanza mía, y castillo mío; Mi Dios, en quien confiaré.",
        },
        "pt": {
            "title": "Salmo 91 Oração da Noite para Dormir em Paz e Proteção Divina",
            "hook": "Aquele que habita no esconderijo do Altíssimo, à sombra do Onipotente descansará. Direi do Senhor: Ele é o meu Deus, o meu refúgio, a minha fortaleza, e nele confiarei.",
        },
    },
    "psalm 23": {
        "es": {
            "title": "Salmo 23 El Señor Es Mi Pastor | Oración Nocturna de Paz y Descanso",
            "hook": "Jehová es mi pastor; nada me faltará. En lugares de delicados pastos me hará descansar; Junto a aguas de reposo me pastoreará. Confortará mi alma.",
        },
        "pt": {
            "title": "Salmo 23 O Senhor É Meu Pastor | Oração da Noite para Paz e Descanso",
            "hook": "O Senhor é o meu pastor, nada me faltará. Deitar-me faz em verdes pastos, guia-me mansamente a águas tranquilas. Refrigera a minha alma.",
        },
    },
    "psalm 121": {
        "es": {
            "title": "Salmo 121 El Que Te Guarda No Dormirá | Oración Antes de Dormir",
            "hook": "Alzaré mis ojos a los montes; ¿De dónde vendrá mi socorro? Mi socorro viene de Jehová, Que hizo los cielos y la tierra. No se dormirá el que te guarda.",
        },
        "pt": {
            "title": "Salmo 121 Aquele Que Te Guarda Não Dormirá | Oração da Noite",
            "hook": "Levantarei os meus olhos para os montes, de onde vem o meu socorro. O meu socorro vem do Senhor que fez o céu e a terra. Aquele que te guarda não dormitará.",
        },
    },
    "psalm 27": {
        "es": {
            "title": "Salmo 27 El Señor Es Mi Luz | Oración de la Noche Sin Temor",
            "hook": "Jehová es mi luz y mi salvación; ¿de quién temeré? Jehová es la fortaleza de mi vida; ¿de quién he de atemorizarme?",
        },
        "pt": {
            "title": "Salmo 27 O Senhor É Minha Luz | Oração da Noite Sem Medo",
            "hook": "O Senhor é a minha luz e a minha salvação; a quem temerei? O Senhor é a força da minha vida; de quem me recearei?",
        },
    },
    "psalm 46": {
        "es": {
            "title": "Salmo 46 Dios Es Nuestro Amparo y Fortaleza | Oración para Dormir",
            "hook": "Dios es nuestro amparo y fortaleza, nuestro pronto auxilio en las tribulaciones. Estad quietos, y conoced que yo soy Dios.",
        },
        "pt": {
            "title": "Salmo 46 Deus É o Nosso Refúgio e Fortaleza | Oração para Dormir",
            "hook": "Deus é o nosso refúgio e fortaleza, socorro bem presente na angústia. Aquietai-vos, e sabei que eu sou Deus.",
        },
    },
    "psalm 34": {
        "es": {
            "title": "Salmo 34 El Ángel del Señor Acampa Alrededor | Oración Nocturna",
            "hook": "El ángel de Jehová acampa alrededor de los que le temen, y los defiende. Gustad, y ved que es bueno Jehová.",
        },
        "pt": {
            "title": "Salmo 34 O Anjo do Senhor Acampa ao Seu Redor | Oração da Noite",
            "hook": "O anjo do Senhor acampa-se ao redor dos que o temem, e os livra. Provai, e vede que o Senhor é bom.",
        },
    },
    "psalm 4": {
        "es": {
            "title": "Salmo 4:8 En Paz Me Acostaré y Asimismo Dormiré | Oración Nocturna",
            "hook": "En paz me acostaré, y asimismo dormiré; porque solo tú, Jehová, me haces vivir confiado.",
        },
        "pt": {
            "title": "Salmo 4:8 Em Paz Me Deito e Logo Adormeço | Oração para Dormir",
            "hook": "Em paz também me deitarei e dormirei, porque só tu, Senhor, me fazes habitar em segurança.",
        },
    },
    "psalm 3": {
        "es": {
            "title": "Salmo 3:3-5 Yo Me Acosté y Dormí | Escudo y Paz en la Noche",
            "hook": "Mas tú, Jehová, eres escudo alrededor de mí; mi gloria, y el que levanta mi cabeza. Yo me acosté y dormí, y desperté, porque Jehová me sustentaba.",
        },
        "pt": {
            "title": "Salmo 3:3-5 Eu Me Deitei e Dormi | Escudo e Paz na Noite",
            "hook": "Mas tu, Senhor, és um escudo para mim, a minha glória, e o que exalta a minha cabeça. Eu me deitei e dormi; acordei, porque o Senhor me sustentou.",
        },
    },
    "psalm 16": {
        "es": {
            "title": "Salmo 16:7-8 Consejo de Dios en la Noche | Oración para Dormir",
            "hook": "Bendeciré a Jehová que me aconseja; aun en las noches me enseña mi conciencia. A Jehová he puesto siempre delante de mí.",
        },
        "pt": {
            "title": "Salmo 16:7-8 Conselho de Deus na Noite | Oração Antes de Dormir",
            "hook": "Louvarei ao Senhor que me aconselha; até os meus rins me ensinam de noite. Tenho posto o Senhor continuamente diante de mim.",
        },
    },
    "psalm 18": {
        "es": {
            "title": "Salmo 18:2 Jehová Roca Mía y Castillo Mío | Oración de Fortaleza",
            "hook": "Jehová, roca mía y castillo mío, y mi libertador; Dios mío, fortaleza mía, en él confiaré.",
        },
        "pt": {
            "title": "Salmo 18:2 O Senhor É a Minha Rocha e Fortaleza | Oração da Noite",
            "hook": "O Senhor é o meu rochedo, e o meu lugar forte, e o meu libertador; o meu Deus, a minha fortaleza, em quem confio.",
        },
    },
    "psalm 31": {
        "es": {
            "title": "Salmo 31:5 En Tu Mano Encomiendo Mi Espíritu | Oración Nocturna",
            "hook": "En tu mano encomiendo mi espíritu; tú me has redimido, oh Jehová, Dios de verdad.",
        },
        "pt": {
            "title": "Salmo 31:5 Nas Tuas Mãos Entrego o Meu Espírito | Oração da Noite",
            "hook": "Nas tuas mãos encomendo o meu espírito; tu me remiste, Senhor Deus da verdade.",
        },
    },
    "psalm 37": {
        "es": {
            "title": "Salmo 37:7 Guarda Silencio Ante Dios y Descansa | Oración de Paz",
            "hook": "Guarda silencio ante Jehová, y espera en él. Confía en Jehová, y haz el bien.",
        },
        "pt": {
            "title": "Salmo 37:7 Descansa no Senhor e Espera Nele | Oração de Paz",
            "hook": "Descansa no Senhor, e espera nele. Entrega o teu caminho ao Senhor; confia nele, e ele o fará.",
        },
    },
    "psalm 63": {
        "es": {
            "title": "Salmo 63:6-7 Bajo la Sombra de Tus Alas en Mi Lecho | Oración",
            "hook": "Cuando me acuerde de ti en mi lecho, cuando medite en ti en las vigilias de la noche; porque has sido mi socorro.",
        },
        "pt": {
            "title": "Salmo 63:6-7 À Sombra das Tuas Asas no Meu Leito | Oração",
            "hook": "Quando me lembrar de ti na minha cama, e meditar em ti nas vigílias da noite; porque tu tens sido o meu auxílio.",
        },
    },
    "psalm 139": {
        "es": {
            "title": "Salmo 139:11-12 La Noche Resplandece Como el Día | Oración",
            "hook": "Aun las tinieblas no encubren de ti, y la noche resplandece como el día; lo mismo te son las tinieblas que la luz.",
        },
        "pt": {
            "title": "Salmo 139:11-12 A Noite Resplandece Como o Dia | Oração de Paz",
            "hook": "Até as próprias trevas não te serão escuras: de noite resplandecerá como o dia; as trevas e a luz são para ti a mesma coisa.",
        },
    },
    "proverbs 3": {
        "es": {
            "title": "Proverbios 3:24 Cuando Te Acuestes Tu Sueño Será Grato | Oración",
            "hook": "Cuando te acuestes, no tendrás temor, sino que te acostarás, y tu sueño será grato.",
        },
        "pt": {
            "title": "Provérbios 3:24 Quando Te Deitares o Teu Sono Será Suave | Oração",
            "hook": "Quando te deitares, não temerás; sim, tu te deitarás, e o teu sono será suave.",
        },
    },
    "isaiah 26": {
        "es": {
            "title": "Isaías 26:3 Tú Guardarás en Completa Paz | Oración para la Mente",
            "hook": "Tú guardarás en completa paz a aquel cuyo pensamiento en ti persevera; porque en ti ha confiado.",
        },
        "pt": {
            "title": "Isaías 26:3 Tu Conservarás em Perfeita Paz | Oração para a Mente",
            "hook": "Tu conservarás em paz aquele cuja mente está firme em ti; porque ele confia em ti.",
        },
    },
    "isaiah 41": {
        "es": {
            "title": "Isaías 41:10 No Temas Porque Yo Estoy Contigo | Oración Nocturna",
            "hook": "No temas, porque yo estoy contigo; no desmayes, porque yo soy tu Dios que te esfuerzo; siempre te ayudaré.",
        },
        "pt": {
            "title": "Isaías 41:10 Não Temas Porque Eu Sou Contigo | Oração da Noite",
            "hook": "Não temas, porque eu sou contigo; não te assombres, porque eu sou teu Deus; eu te fortaleço, e te ajudo.",
        },
    },
    "matthew 11": {
        "es": {
            "title": "Mateo 11:28 Venid a Mí y Os Haré Descansar | Oración para Dormir",
            "hook": "Venid a mí todos los que estáis trabajados y cargados, y yo os haré descansar.",
        },
        "pt": {
            "title": "Mateus 11:28 Vinde a Mim e Eu Vos Aliviarei | Oração para Dormir",
            "hook": "Vinde a mim, todos os que estais cansados e oprimidos, e eu vos aliviarei.",
        },
    },
    "john 14": {
        "es": {
            "title": "Juan 14:27 Mi Paz Os Doy, No Se Turbe Tu Corazón | Oración",
            "hook": "La paz os dejo, mi paz os doy; yo no os la doy como el mundo la da. No se turbe vuestro corazón, ni tenga miedo.",
        },
        "pt": {
            "title": "João 14:27 Deixo-vos a Minha Paz | Oração da Noite Sem Medo",
            "hook": "Deixo-vos a paz, a minha paz vos dou; não vo-la dou como o mundo a dá. Não se turbe o vosso coração, nem se atemorize.",
        },
    },
    "philippians 4": {
        "es": {
            "title": "Filipenses 4:6-7 La Paz de Dios Guardará Tu Mente | Oración",
            "hook": "Y la paz de Dios, que sobrepasa todo entendimiento, guardará vuestros corazones y vuestros pensamientos en Cristo Jesús.",
        },
        "pt": {
            "title": "Filipenses 4:6-7 A Paz de Deus Guardará a Sua Mente | Oração",
            "hook": "E a paz de Deus, que excede todo o entendimento, guardará os vossos corações e os vossos sentimentos em Cristo Jesus.",
        },
    },
    "2 timothy 1": {
        "es": {
            "title": "2 Timoteo 1:7 Poder, Amor y Dominio Propio | Oración Sin Temor",
            "hook": "Porque no nos ha dado Dios espíritu de cobardía, sino de poder, de amor y de dominio propio.",
        },
        "pt": {
            "title": "2 Timóteo 1:7 Poder, Amor e Moderação | Oração Contra o Medo",
            "hook": "Porque Deus não nos deu o espírito de temor, mas de fortaleza, e de amor, e de moderação.",
        },
    },
    "1 peter 5": {
        "es": {
            "title": "1 Pedro 5:7 Echando Toda Ansiedad Sobre Él | Oración Nocturna",
            "hook": "Echando toda vuestra ansiedad sobre él, porque él tiene cuidado de vosotros.",
        },
        "pt": {
            "title": "1 Pedro 5:7 Lançando Sobre Ele Toda a Ansiedade | Oração da Noite",
            "hook": "Lançando sobre ele toda a vossa ansiedade, porque ele tem cuidado de vós.",
        },
    },
    "numbers 6": {
        "es": {
            "title": "Números 6:24-26 Jehová Te Bendiga y Te Guarde | Bendición Nocturna",
            "hook": "Jehová te bendiga, y te guarde; Jehová haga resplandecer su rostro sobre ti, y ponga en ti paz.",
        },
        "pt": {
            "title": "Números 6:24-26 O Senhor Te Abençoe e Te Guarde | Bênção da Noite",
            "hook": "O Senhor te abençoe e te guarde; o Senhor faça resplandecer o seu rosto sobre ti e te dê a paz.",
        },
    },
}

_LANG_INVITATION = {
    "es": "Escucha esta oración bíblica antes de dormir para recibir la paz profunda de Dios y protección sobre tu hogar.",
    "pt": "Ouça esta oração bíblica antes de dormir para receber a paz profunda de Deus e proteção sobre o seu lar.",
}


def _localized_selar_header(lang_code: str, existing_desc: str) -> str:
    if not SELAR_JOURNAL_URL or SELAR_JOURNAL_URL in (existing_desc or ""):
        return ""
    if lang_code == "pt":
        return (
            f"📖 Diário de Oração de 30 Noites (PDF Imprimível): {SELAR_JOURNAL_URL}\n"
            f"🤍 Apoio Voluntário ao Ministério: {SELAR_STORE_URL}\n\n"
        )
    return (
        f"📖 Diario de Oración de 30 Noches (PDF Imprimible): {SELAR_JOURNAL_URL}\n"
        f"🤍 Apoyo Voluntario al Ministerio: {SELAR_STORE_URL}\n\n"
    )


def build_metadata_localizations(
    title: str,
    description: str,
    niche: str = "faith and prayer",
) -> dict[str, dict[str, str]]:
    """Build localized Spanish (`es`) and Portuguese (`pt`) metadata within API byte limits."""
    niche_lower = (niche or "").lower()
    if any(k in niche_lower for k in ("finance", "business", "economics", "corporate")):
        return {}

    title_lower = (title or "").lower()
    matched_key = None

    # Sort keys longest-first + word boundary without trailing digits so 'psalm 3' never matches 'psalm 34'
    for key in sorted(LOCALIZATION_DICTIONARY.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}(?!\d)", title_lower):
            matched_key = key
            break

    if not matched_key:
        es_selar = _localized_selar_header("es", description)
        pt_selar = _localized_selar_header("pt", description)
        return {
            "es": {
                "title": smart_truncate_title("Oración de la Noche para Dormir en Paz | The Secret Place", 95),
                "description": truncate_utf8_bytes(
                    "Oración nocturna de protección divina y paz. Descansa bajo la sombra del Altísimo.\n\n"
                    f"{es_selar}"
                    f"{description}",
                    max_bytes=4900,
                ),
            },
            "pt": {
                "title": smart_truncate_title("Oração da Noite para Dormir em Paz | The Secret Place", 95),
                "description": truncate_utf8_bytes(
                    "Oração poderosa da noite para proteção e paz espiritual. Descanse sob as asas de Deus.\n\n"
                    f"{pt_selar}"
                    f"{description}",
                    max_bytes=4900,
                ),
            },
        }

    loc_data = LOCALIZATION_DICTIONARY[matched_key]
    localizations: dict[str, dict[str, str]] = {}

    for lang_code, trans in loc_data.items():
        loc_title = smart_truncate_title(trans["title"], 95)
        invite = _LANG_INVITATION.get(lang_code, _LANG_INVITATION["es"])
        selar_hdr = _localized_selar_header(lang_code, description)
        loc_desc = truncate_utf8_bytes(
            f"{trans['hook']}\n\n{invite}\n\n{selar_hdr}{description}",
            max_bytes=4900,
        )
        localizations[lang_code] = {
            "title": loc_title,
            "description": loc_desc,
        }

    return localizations
