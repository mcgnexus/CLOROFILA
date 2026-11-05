/* Configuracion del grafico de espectro (Chart.js) - FASE 2.
   Dos series superpuestas: medido (barras) y prediccion del gemelo (linea). */

// Etiquetas con longitud de onda para cada canal.
const ETIQUETAS = {
  F1: "F1·415nm", F2: "F2·445nm", F3: "F3·480nm", F4: "F4·515nm",
  F5: "F5·555nm", F6: "F6·590nm", F7: "F7·630nm", F8: "F8·680nm",
  Clear: "Clear", NIR: "NIR·910nm",
};

let graficoEspectro = null;

/** Crea el grafico combinado una sola vez. */
function crearGraficoEspectro(ordenCanales) {
  const ctx = document.getElementById("grafico-espectro");
  if (graficoEspectro) return graficoEspectro;

  graficoEspectro = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ordenCanales.map((c) => ETIQUETAS[c] || c),
      datasets: [
        {
          label: "Medido (simulado)",
          data: ordenCanales.map(() => 0),
          borderWidth: 1,
        },
        {
          label: "Gemelo (predicción)",
          type: "line",
          data: ordenCanales.map(() => 0),
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      animation: false, // sin animacion: se actualiza cada segundo
      scales: { y: { beginAtZero: true, title: { display: true, text: "Cuentas" } } },
    },
  });
  return graficoEspectro;
}

/** Actualiza ambas series con un mensaje del WebSocket (Fase 2).
 *  Mantiene compatibilidad con mensajes Fase 1 (solo "canales"). */
function actualizarGrafico(msg) {
  const orden = msg.orden_canales;
  crearGraficoEspectro(orden);
  graficoEspectro.data.labels = orden.map((c) => ETIQUETAS[c] || c);
  graficoEspectro.data.datasets[0].data = orden.map((c) => msg.canales[c]);
  const pred = msg.prediccion || {};
  graficoEspectro.data.datasets[1].data = orden.map((c) => pred[c] ?? null);
  graficoEspectro.update();
}
