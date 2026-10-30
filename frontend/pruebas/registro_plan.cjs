// Guarda en resultados_plan_<parte>.json lo que observó cada caso del plan de pruebas (documento 14).
// El script scripts/rellenar_plan.py junta estos archivos con los del servidor y completa el Excel.
const fs = require("fs");
const path = require("path");

function abrir(parte) {
  const archivo = process.env.RESULTADOS_PLAN || path.join(__dirname, `resultados_plan_${parte}.json`);
  let datos = {};
  try { datos = JSON.parse(fs.readFileSync(archivo, "utf8")); } catch { datos = {}; }
  return {
    anotar(id, aprobado, texto, estado) {
      datos[id] = { estado: estado || (aprobado ? "Aprobado" : "Falló"), obtenido: texto };
      fs.writeFileSync(archivo, JSON.stringify(datos, null, 1));
    },
    reiniciar() { datos = {}; fs.writeFileSync(archivo, "{}"); },
  };
}
module.exports = { abrir };
