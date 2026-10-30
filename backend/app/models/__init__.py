"""Modelos de SQLAlchemy: una clase por tabla del modelo entidad-relación (documento 12)."""
from app.models.usuario import IntentoIngreso, Otp, Token, Usuario  # noqa: F401
from app.models.cultivo import Cultivo  # noqa: F401
from app.models.finca import Finca  # noqa: F401
from app.models.ciclo import Ciclo  # noqa: F401
from app.models.ciclo_cultivo import CicloCultivo  # noqa: F401
from app.models.ficha_tecnica import FichaTecnica  # noqa: F401
from app.models.movimientos import Gasto, Ingreso, Jornal  # noqa: F401
