# Sembrando Futuro (PWA + API)

Unicomfacauca · Calidad de Software. Implementa lo definido en los documentos 01–23 (carpeta `docs/`).
Backend FastAPI (`/api/v1`) y PWA offline-first sin paso de compilación, servida por el mismo FastAPI.

## Desarrollo local
```bash
cd backend
pyenv install 3.14.7 && pyenv local 3.14.7
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                                    # ajuste DB_* y CLAVE_SECRETA
# MariaDB (WampServer, puerto 3307):  CREATE DATABASE sembrando CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
alembic upgrade head
python -m app.cli cargar_semilla                        # catálogo de cultivos
python -m app.cli crear_admin                           # pide correo/clave (o ADMIN_CLAVE)
python -m app.cli cargar_prueba [--restablecer]           # opcional: datos del doc. 19 (--restablecer borra antes las cuentas de prueba)
uvicorn app.main:app --reload                           # http://localhost:8000  (PWA)
```
Con `ENTORNO=pruebas` el código OTP es fijo (482915) y no se envía correo. En `desarrollo` sin `BREVO_API_KEY` el código se escribe en el log.

## Pruebas
```bash
cd backend && pytest -q                 # 382 pruebas (incluye el plan del documento 14, caja blanca CB-01..CB-28 y migración)
cd frontend && node --test              # 44 pruebas de cálculos y del plan (node:test, incluido en Node; sin Vitest)
# Calidad del código (documentos 22 y 23):
cd backend && flake8 app tests alembic  # estilo y complejidad máxima de 10 (.flake8)
cd backend && pytest -q --cov=app --cov-branch --cov-fail-under=80
cd frontend && npm install && npm run lint && npm run test:cov   # ESLint (complejidad ≤ 10) y cobertura de Node
# E2E (Playwright + Chromium) contra un servidor local con ENTORNO=pruebas:
cd frontend && node pruebas/e2e.cjs && node pruebas/e2e_datos_prueba.cjs
# Plan de pruebas del documento 14 (deja las columnas «Estado» y «Resultado obtenido» del Excel):
#   servidor con ENTORNO=pruebas, LIMITE_REGISTRO e LIMITE_INGRESO altos, cargar_prueba y el administrador de prueba
cd backend && pytest -q                                 # parte del servidor y caja blanca → tests/resultados_plan.json
cd frontend && node --test && node pruebas/e2e_plan.cjs # partes del dispositivo y de la pantalla → pruebas/resultados_plan_*.json
python scripts/rellenar_plan.py                         # completa docs/14_Matriz_Trazabilidad_y_Plan_Pruebas_final.xlsx (necesita openpyxl)
```
Los casos que no se pueden automatizar (usabilidad con agricultores, Lighthouse, OWASP ZAP, SSL Labs, disponibilidad mensual, bitácoras PSP y la prueba de humo en el sitio publicado) quedan «Pendiente» con el motivo.

## Despliegue (Render + Aiven + Brevo)
1. Cree la base MySQL en Aiven; copie host, puerto, nombre, usuario y clave (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) y guarde su certificado como `backend/ca.pem`.
2. Cree la cuenta Brevo, verifique el remitente y genere `BREVO_API_KEY`.
3. En Render: *New → Blueprint* con este repositorio (`render.yaml`). Defina las variables marcadas `sync: false`.
4. El plan gratuito de Render no ofrece *Shell*: cree el administrador (y, si lo desea, los datos de prueba) una sola vez desde su computador, con las mismas variables `DB_*` en el `.env`: `python -m app.cli crear_admin` y `python -m app.cli cargar_prueba`.

## Administración (sin pantallas)
La cuenta de Administrador no tiene pantallas en la PWA; se opera por consola en el servidor:
```bash
python -m app.cli listar_cuentas [--estado ACTIVA|PENDIENTE]
python -m app.cli resumen_cuenta --correo agricultor@correo.com
python -m app.cli cambiar_clave --correo agricultor@correo.com      # pide la clave nueva (o CLAVE_NUEVA)
python -m app.cli eliminar_cuenta --correo agricultor@correo.com
python -m app.cli cargar_semilla [--archivo catalogo.json]        # edita el catálogo y las fichas técnicas
```
Sin Docker, sin captcha, sin token en la URL ni `X-App-Key`.

## Estructura
`backend/` API, modelos, migraciones Alembic (`alembic/versions/0001_inicial.py`), CLI, pruebas · `frontend/` PWA (JavaScript de módulos sin paso de compilación, IndexedDB con un envoltorio propio, Service Worker) · `datos/` semilla y datos de prueba · `docs/` documentación.

## Límites conocidos de esta entrega
- Probado en el entorno de desarrollo con SQLite y Chromium; **no** ejecutado aún sobre Python 3.14.7, MariaDB/Aiven, argon2-cffi real, PyMySQL, ESLint ni SonarCloud (se configuran en el CI, pero aún no se ejecutaron). La PWA no usa Dexie: `src/db/db.js` es un envoltorio propio de IndexedDB.
- `requirements.txt` fija mínimos; ejecute `pip freeze > requirements.lock` tras instalar.
- La tipografía Atkinson no se incluye (usa una fuente del sistema).
- Los límites de tasa son en memoria (un solo proceso).
