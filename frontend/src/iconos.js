// Íconos SVG en línea (trazo con el estilo de Lucide, licencia ISC). Van dentro del HTML: funcionan sin conexión y toman el color del texto.
const TRAZOS = {
  inicio: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
  mapa: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z"/><path d="M9 4v14M15 6v14"/>',
  calculadora: '<rect x="5" y="2.5" width="14" height="19" rx="2"/><path d="M8.5 6.5h7"/><path d="M8.5 11h.01M12 11h.01M15.5 11h.01M8.5 14.5h.01M12 14.5h.01M15.5 14.5h.01M8.5 18h.01M12 18h.01M15.5 18h.01"/>',
  libro: '<path d="M4 19.5V5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2.5Z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-3"/>',
  recibo: '<path d="M5 2v20l2.5-1.5L10 22l2-1.5 2 1.5 2.5-1.5L19 22V2l-2.5 1.5L14 2l-2 1.5L10 2 7.5 3.5 5 2Z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  personas: '<circle cx="9" cy="7" r="3.5"/><path d="M2.5 21v-1.5A5.5 5.5 0 0 1 8 14h2a5.5 5.5 0 0 1 5.5 5.5V21"/><path d="M16 3.6a3.5 3.5 0 0 1 0 6.8M21.5 21v-1.5a5.5 5.5 0 0 0-3.5-5.1"/>',
  subida: '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
  bajada: '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
  area: '<path d="M3 3h18v18H3z" stroke-dasharray="3 3"/><path d="M7 7h10v10H7z"/>',
  brote: '<path d="M12 21v-9"/><path d="M12 12c0-4 3-7 8-7 0 5-3 7-8 7Z"/><path d="M12 14c0-3.3-2.5-6-7-6 0 4 2.5 6 7 6Z"/>',
  mas: '<path d="M12 5v14M5 12h14"/>',
  flecha: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  atras: '<path d="m15 18-6-6 6-6"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  calendario: '<rect x="3" y="4.5" width="18" height="17" rx="2"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
  grafica: '<path d="M3 3v18h18"/><path d="M7 16v-4M12 16V8M17 16v-7"/>',
  usuario: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>',
};

/** Devuelve el SVG del ícono; el texto de la pantalla nunca depende de él (aria-hidden). */
export const ico = (nombre, tam = 22, clase = "") => `<svg class="ico ${clase}" width="${tam}" height="${tam}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${TRAZOS[nombre] || ""}</svg>`;
