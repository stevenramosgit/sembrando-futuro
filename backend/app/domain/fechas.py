"""Fechas: hoy en Colombia (UTC−5, sin horario de verano), lectura estricta de AAAA-MM-DD y límites de las reglas V-29, V-47 y V-48."""
import re
from datetime import date, datetime, timedelta, timezone

COLOMBIA = timezone(timedelta(hours=-5))
INICIO_SIEMBRAS = date(2020, 1, 1)
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def hoy(ahora_utc: datetime | None = None) -> date:
    base = ahora_utc.replace(tzinfo=timezone.utc) if ahora_utc is not None else datetime.now(timezone.utc)
    return base.astimezone(COLOMBIA).date()


def leer_fecha(valor) -> date | None:
    """Devuelve la fecha si el texto es AAAA-MM-DD y existe en el calendario; si no, None (V-28)."""
    if not isinstance(valor, str) or not _ISO.match(valor.strip()):
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        return None


def sumar_anios(d: date, anios: int) -> date:
    try:
        return d.replace(year=d.year + anios)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year + anios, day=28)


def un_anio_despues(d: date) -> date:
    return sumar_anios(d, 1)


def leer_fecha_hora(valor) -> datetime | None:
    """ISO 8601 en UTC ('2026-10-26T13:58:10.123Z' o con desplazamiento). Devuelve UTC sin zona."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if texto.endswith(("Z", "z")):
        texto = texto[:-1] + "+00:00"
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        return None
    return momento.astimezone(timezone.utc).replace(tzinfo=None)


def a_iso(momento: datetime) -> str:
    return momento.isoformat(timespec="milliseconds") + "Z"
