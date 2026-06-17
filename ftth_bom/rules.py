from __future__ import annotations

import math
import re
import unicodedata


FX_RE = re.compile(r"\b[FX]/\d{6,}\b", re.IGNORECASE)
OPP_RE = re.compile(r"\bOPP[\s_/-]*0*(\d{1,4})\b", re.IGNORECASE)
OSD_RE = re.compile(r"\bOSD[\s_/-]*0*(\d{1,4})\b", re.IGNORECASE)
NON_ORDERABLE_MATERIAL_CLASSES = {"ADSS_2J"}


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    text = text.translate(str.maketrans({"ł": "l", "Ł": "L"}))
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def normalize_key(value: object) -> str:
    return normalize_text(value).lower()


def normalize_match(value: object) -> str:
    return re.sub(r"[^a-z0-9/]+", " ", normalize_key(value)).strip()


def fmt_sap(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    try:
        number = float(text)
    except ValueError:
        return text[:-2] if text.endswith(".0") else text
    if math.isnan(number):
        return ""
    return str(int(number)) if number.is_integer() else text


def as_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number):
        return default
    return number


def as_int(value: object) -> int | None:
    number = as_float(value, default=float("nan"))
    if math.isnan(number):
        return None
    return int(number)


def extract_fx(value: object) -> list[str]:
    text = normalize_text(value).upper()
    return sorted(set(match.upper() for match in FX_RE.findall(text)))


def extract_project_tokens(*values: object) -> list[str]:
    tokens: set[str] = set()
    for value in values:
        text = normalize_text(value).upper()
        for match in OPP_RE.finditer(text):
            num = int(match.group(1))
            tokens.add(f"OPP {num:04d}")
            tokens.add(f"OPP{num:04d}")
            tokens.add(f"OPP {num}")
        for match in OSD_RE.finditer(text):
            num = int(match.group(1))
            tokens.add(f"OSD {num:04d}")
            tokens.add(f"OSD{num:04d}")
    return sorted(tokens)


def classify_material_name(name: object, sap: object = "") -> str:
    text = normalize_match(f"{name} {sap}").upper()
    compact = text.replace(" ", "")

    if "FP MR G 12/8" in text or "MIKRORURKA 12/8" in text or "MIKRORURKA 12 8" in text:
        return "MIKRORURKA_12_8"
    if "FP MR G 14/10" in text or "MIKRORURKA 14/10" in text or "MIKRORURKA 14 10" in text:
        return "MIKRORURKA_14_10"
    if "SSC2110" in compact:
        return "MUFA_SSC2110"
    if "SPL" in compact and ("1X64" in compact or "164" in compact):
        return "SPLITTER_1X64"
    if "PSB H 144" in text and "FUNDAMENT" not in text and "UCHWYT" not in text:
        return "PSB_H_144"
    if "FUNDAMENT" in text and "PSB H" in text:
        return "FUNDAMENT_PSB_H"
    if ("SUS PH S" in text or "SUS PHS" in compact or ("SUS PH" in text and "BEZ KOMUTACJI" in text)) and "ZEST" not in text:
        return "SUS_PH_S"
    if "UCHWYT" in text and "DYSTANS" in text and "RUR" in text:
        return "DYSTANS_HDPE_UV"
    if "DYSTANS" in text and "OAP" in text:
        return "DYSTANS_OAP"
    if "STELAZ" in text and "ZAPAS" in text:
        return "STELAZ_ZAPASU"
    if "DAC" in text and "12J" in compact:
        return "DAC_12J"
    if "DAC" in text and "6J" in compact:
        return "DAC_6J"
    if "DAC" in text and "4J" in compact:
        # Regula magazynowa: DAC 4J zamawiamy jako DAC 6J.
        return "DAC_6J"
    if "DAC" in text and "2J" in compact:
        return "DAC_2J"
    if "ADSS" in text and "12J" in compact:
        return "ADSS_12J"
    if "ADSS" in text and "24J" in compact:
        return "ADSS_24J"
    if "ADSS" in text and "36" in compact:
        return "ADSS_36J"
    if "ADSS" in text and "2J" in compact:
        return "ADSS_2J"
    is_micro_cable = "MIKROKABEL" in text or "MI MKF" in text or "MIMKF" in compact
    if is_micro_cable and "12J" in compact:
        return "MIKROKABEL_12J"
    if is_micro_cable and "24J" in compact:
        return "MIKROKABEL_24J"
    if is_micro_cable and "36J" in compact:
        return "MIKROKABEL_36J"
    if is_micro_cable and "48J" in compact:
        return "MIKROKABEL_48J"
    if is_micro_cable and "72J" in compact:
        return "MIKROKABEL_72J"
    if is_micro_cable and ("96J" in compact or "96X" in compact):
        return "MIKROKABEL_96J"
    if is_micro_cable and "144" in compact:
        return "MIKROKABEL_144J"
    if "MIKRORURKA" in text and ("12/8" in text or "12 8" in text):
        return "MIKRORURKA_12_8"
    if "MIKRORURKA" in text and ("14/10" in text or "14 10" in text):
        return "MIKRORURKA_14_10"
    if "HDPE-UV" in text or ("HDPE" in text and "UV" in text):
        return "HDPE_UV_40"
    if "HDPE" in text and ("40" in text or "FI40" in compact):
        return "HDPE_40"
    if "PIGTAIL" in text and "SC/APC" in text:
        return "PIGTAIL_SC_APC"
    if "ADAPTER" in text and "SC/APC" in text:
        return "ADAPTER_SC_APC"
    if ("OSLONKA" in text and "SPAW" in text) or "OS45" in compact:
        return "OSLONKA_SPAWU"
    if "KAPTUREK" in text and "DAC" in text:
        return "KAPTUREK_DAC"
    if "NAKLEJKA" in text and "S I" in text and "50X72" in compact:
        return "NAKLEJKA_SI_50X72"
    if ("PIANKA" in text or "MASA USZCZELNIAJACA" in text) and "MD" in text and "310" in compact:
        return "PIANKA_MD"
    if "HDPE D" in text and ("FI110" in compact or "110X100" in compact):
        return "HDPE_D_110"
    if "TASMA" in text and ("OST" in text or "OSTRZEGAWCZA" in text) and "TKT" in text:
        return "TASMA_OSTRZEGAWCZA"
    if "ZAMEK ABLOY" in text and "CL704B" in compact:
        return "ZAMEK_ABLOY"
    if "HAK" in text and "UNIWERSAL" in text:
        return "HAK_UNIWERSALNY"
    if "UCHWYT" in text and "ODCIAG" in text:
        return "UCHWYT_ODCIAGOWY"
    if "UCHWYT" in text and "PRZELOT" in text:
        return "UCHWYT_PRZELOTOWY"
    if "TASMA STAL" in text and ("TSM/10" in compact or "10MM" in compact):
        return "TASMA_STALOWA_10MM"
    if "TASMA STAL" in text:
        return "TASMA_STALOWA"
    if "KLAMRA" in text and "TASM" in text:
        return "KLAMRA_TASMY"
    if "ZLACZKA" in text and ("12MM" in compact or "12/8" in compact):
        return "ZLACZKA_MIKRO_12"
    if "ZLACZKA" in text and ("14MM" in compact or "14/10" in compact):
        return "ZLACZKA_MIKRO_14"
    if "SPLITTER" in text or "SPLITER" in text or "S PL" in text or compact.startswith("SPL"):
        return "SPLITTER"
    if "OAP" in text and "48" in text:
        return "OAP_48"
    if "OAP" in text and "24" in text:
        return "OAP_24"
    if "OAP" in text and "8" in text:
        return "OAP_8"
    if "OAP" in text:
        return "OAP"
    if "FIST" in text or "MUFA" in text or "BPEO" in text or "BEPO" in text:
        return "MUFA"
    return "INNE"


def is_orderable_material_class(material_class: str) -> bool:
    return material_class not in NON_ORDERABLE_MATERIAL_CLASSES


def preferred_category(material_class: str) -> str:
    if material_class.startswith(("DAC", "ADSS", "MIKROKABEL")):
        return "Kable"
    if material_class.startswith("MIKRORURKA") or material_class.startswith("HDPE"):
        return "Kanalizacja"
    if material_class in {
        "PIGTAIL_SC_APC",
        "ADAPTER_SC_APC",
        "OSLONKA_SPAWU",
        "KAPTUREK_DAC",
        "NAKLEJKA_SI_50X72",
        "PIANKA_MD",
        "TASMA_OSTRZEGAWCZA",
        "ZLACZKA_MIKRO_12",
        "ZLACZKA_MIKRO_14",
    }:
        return "Osprzęt optyczny"
    if material_class.startswith("UCHWYT") or material_class in {
        "TASMA_STALOWA",
        "TASMA_STALOWA_10MM",
        "KLAMRA_TASMY",
        "HAK_UNIWERSALNY",
        "DYSTANS_OAP",
        "DYSTANS_HDPE_UV",
    }:
        return "Osprzęt napowietrzny"
    if material_class in {
        "SPLITTER",
        "SPLITTER_1X64",
        "MUFA",
        "MUFA_SSC2110",
        "PSB_H_144",
        "SUS_PH_S",
        "FUNDAMENT_PSB_H",
        "ZAMEK_ABLOY",
    } or material_class.startswith("OAP"):
        return "Punkty pasywne"
    return "Inne"


def round_order_length(value: float) -> int:
    if value <= 0:
        return 0
    if value <= 200:
        step = 10
    elif value <= 1000:
        step = 50
    else:
        step = 100
    return int(math.ceil(value / step) * step)


def round_order_length_with_reserve(value: float, reserve: float = 0.03, step: int = 5) -> int:
    if value <= 0:
        return 0
    return int(math.ceil((value * (1 + reserve)) / step) * step)


def normalize_qty(value: float | int) -> float | int:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value
