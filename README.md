# Sembrando Futuro (PWA + API)

Unicomfacauca · Calidad de Software. Implementa lo definido en los documentos 01–24 (carpeta `docs/`).
Backend FastAPI (`/api/v1`) y PWA offline-first sin paso de compilación, servida por el mismo FastAPI.

## Desarrollo local
```bash
cd backend
pyenv install 3.14.7 && pyenv local 3.14.7
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                                    # ajuste DB_* y CLAVE_SECRETA
# MySQL 8 local:  CREATE DATABASE sembrando_futuro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
alembic upgrade head
python -m app.cli cargar_semilla                        # catálogo de cultivos
python -m app.cli crear_admin                           # pide correo/clave (o ADMIN_CLAVE)
python -m app.cli cargar_prueba [--restablecer]           # opcional: datos del doc. 19 (--restablecer borra antes las cuentas de prueba)
uvicorn app.main:app --reload                           # http://localhost:8000  (PWA)
```
Con `ENTORNO=pruebas` el código OTP es fijo (482915) y no se envía correo. En `desarrollo` sin `BREVO_API_KEY` el correo no se envía y la terminal lo avisa (el código no se escribe en el registro); para probar sin correo use `ENTORNO=pruebas`.

## Pruebas
```bash
cd backend && pytest -q                 # 412 pruebas (incluye el plan del documento 14, caja blanca CB-01..CB-28 y migración)
cd frontend && node --test              # 47 pruebas de cálculos y del plan (node:test, incluido en Node; sin Vitest)
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
Guía completa paso a paso: `docs/24_Guia_de_Despliegue_y_Sustentacion.docx`.
1. Cree la base MySQL 8 en Aiven; copie host, puerto, nombre, usuario y clave (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) y guarde su certificado (*CA certificate*) como `backend/ca.pem` (es público; se sube al repositorio).
2. Cree la cuenta Brevo, verifique el remitente (ideal: un dominio propio autenticado con SPF y DKIM) y genere `BREVO_API_KEY`.
3. En Render: *New → Blueprint* con este repositorio (`render.yaml`). Defina las variables marcadas `sync: false`; `DOMINIO` admite varios hosts separados por coma (el de onrender.com y el propio).
4. Si falta algo importante, el servicio no arranca y el registro de Render dice qué corregir (`validar_produccion` en `app/core/config.py`).
5. El plan gratuito de Render no ofrece *Shell*: cree el administrador (y, si lo desea, los datos de prueba) una sola vez desde su computador, con las mismas variables `DB_*` y `DB_SSL_CA` en el `.env`: `python -m app.cli crear_admin`.
6. Dominio propio (opcional): en Render, *Settings → Custom Domains*; en el proveedor del dominio, el registro CNAME que Render indique. Agregue el dominio a `DOMINIO`.
7. Compruebe que el límite por IP no se puede saltar: `python scripts/verificar_limite_ip.py https://su-dominio` (ajuste `PROXY_SALTOS` si hace falta).
8. Cree un monitor externo gratuito que consulte `https://su-dominio/api/v1/salud` cada 5 minutos: mide la disponibilidad (RNF-10) y mantiene despiertos Render y Aiven.

## Administración (sin pantallas)
La cuenta de Administrador no tiene pantallas en la PWA; se opera por consola (en Render gratuito, desde su computador con las variables de Aiven) o con los servicios AD-01 a AD-05 de la API:
```bash
python -m app.cli listar_cuentas [--estado ACTIVA|PENDIENTE]
python -m app.cli resumen_cuenta --correo agricultor@correo.com
python -m app.cli cambiar_clave --correo agricultor@correo.com      # pide la clave nueva (o CLAVE_NUEVA)
python -m app.cli eliminar_cuenta --correo agricultor@correo.com
python -m app.cli cargar_semilla [--archivo catalogo.json]        # agrega cultivos nuevos y completa lo que falte (no sobrescribe)
python -m app.cli cargar_semilla --forzar                        # reemplaza el catálogo con los valores del archivo
```
Sin Docker, sin captcha, sin token en la URL ni `X-App-Key`.

## Estructura
`backend/` API, modelos, migraciones Alembic (`alembic/versions/0001_inicial.py` y `0002_proyeccion_cosecha.py`), CLI, pruebas · `frontend/` PWA (JavaScript de módulos sin paso de compilación, Bootstrap 5 CSS e Inter locales, IndexedDB con un envoltorio propio, Service Worker) · `datos/` semilla y datos de prueba · `docs/` documentación.

## Límites conocidos de esta entrega
- Las pruebas automáticas de esta entrega se ejecutaron con SQLite en memoria y Chromium, con Python 3.13; el CI y Render usan Python 3.14.7. El sitio publicado (Render + Aiven MySQL 8 + Brevo) corre con MySQL real. flake8 7.4.1 y ESLint 10.1.0 se ejecutaron localmente el 29 de octubre con 0 errores (el CI usa ESLint 9 con las mismas reglas); SonarCloud y la cobertura oficial con pytest-cov salen de la primera ejecución del CI. `src/db/db.js` es un envoltorio propio de IndexedDB, sin librerías externas.
- `requirements.txt` fija versiones mínimas. El CI guarda `requirements.lock` (artefacto «versiones-backend») con las versiones exactas que pasaron las pruebas: copie ese contenido en `requirements.txt` después de la primera ejecución.
- Interfaz: Bootstrap 5.3.3 (solo CSS, MIT) y tipografía Inter (OFL) van incluidas en `frontend/vendor` y `frontend/fonts`, con licencias en `frontend/vendor/LICENCIAS.txt`; los íconos son SVG propios (`frontend/src/iconos.js`). No hay recursos externos: funciona sin internet.
- Los límites de tasa son en memoria (un solo proceso, como corre en Render gratuito). La posición de la IP real (`PROXY_SALTOS=3`) se comprueba en el sitio publicado con `scripts/verificar_limite_ip.py`.
