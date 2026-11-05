/* Cliente WebSocket del dashboard (Fase 4: PROSPECT-D + ML). */
(() => {
  const badge = document.getElementById("estado-conexion");
  const elUltima = document.getElementById("ultima-lectura");
  const elContador = document.getElementById("contador");
  const elTabla = document.getElementById("tabla-canales");
  const elRmse = document.getElementById("metrica-rmse");
  const elRmseRel = document.getElementById("metrica-rmse-rel");
  const elSesgo = document.getElementById("metrica-sesgo");
  const elIndice = document.getElementById("indice-valor");
  const elBarra = document.getElementById("indice-barra");
  const elAlerta = document.getElementById("alerta-anomalia");
  const elTarjetaComp = document.getElementById("tarjeta-comparacion");
  const elModo = document.getElementById("etiqueta-modo");
  const ctlCab = document.getElementById("control-cab");
  const ctlCw = document.getElementById("control-cw");
  const ctlN = document.getElementById("control-n");
  const elCabVal = document.getElementById("cab-valor");
  const elCwVal = document.getElementById("cw-valor");
  const elNVal = document.getElementById("n-valor");
  const selModo = document.getElementById("selector-modo");
  const btnEstres = document.getElementById("boton-estres");
  const btnSync = document.getElementById("boton-sincronizar");
  const elHojaCab = document.getElementById("hoja-cab");
  const elGemeloCab = document.getElementById("gemelo-cab");
  const elMlCab = document.getElementById("ml-cab");

  let contador = 0;
  let temporizadorReconexion = null;
  let temporizadorSondeo = null;
  let temporizadorEsperaWs = null;
  let transporte = "websocket"; // o "sondeo" si no hay WebSocket (p. ej. Vercel)
  // Un temporizador por clave: cambios rapidos en distintos controles
  // ya no se pisan entre si (antes habia un solo temporizador global).
  const temporizadores = {};
  const INTERVALO_SONDEO = 2000;

  const LONGITUD_TXT = { Clear: "banda ancha" };

  function setEstado(texto, clase) {
    badge.textContent = texto;
    badge.className = `badge ${clase}`;
  }

  /** Envía la configuración al backend (con anti-rebote por clave). */
  async function enviarConfig(datos) {
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos),
      });
      if (!res.ok) console.warn("Config rechazada:", await res.text());
    } catch (err) {
      console.warn("Sin conexión con /api/config:", err);
    }
  }

  function programarEnvio(clave, datos) {
    clearTimeout(temporizadores[clave]);
    temporizadores[clave] = setTimeout(() => enviarConfig(datos), 250);
  }

  // --- Controles (mueven SOLO el gemelo) ---
  ctlCab.addEventListener("input", () => {
    elCabVal.textContent = ctlCab.value;
    programarEnvio("cab", { cab: Number(ctlCab.value) });
  });
  ctlCw.addEventListener("input", () => {
    elCwVal.textContent = Number(ctlCw.value).toFixed(3);
    programarEnvio("cw", { cw: Number(ctlCw.value) });
  });
  ctlN.addEventListener("input", () => {
    elNVal.textContent = Number(ctlN.value).toFixed(1);
    programarEnvio("n", { n: Number(ctlN.value) });
  });
  selModo.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      selModo.querySelectorAll("button").forEach((b) => b.classList.remove("activo"));
      btn.classList.add("activo");
      enviarConfig({ modo: btn.dataset.modo });
    });
  });
  btnEstres.addEventListener("click", () => {
    const activo = btnEstres.classList.toggle("encendido");
    btnEstres.textContent = activo ? "Activado" : "Desactivado";
    enviarConfig({ estres: activo });
  });
  btnSync.addEventListener("click", () => {
    enviarConfig({ sincronizar: true });
    setTimeout(cargarConfig, 400); // relee el gemelo ya alineado
  });

  /** Sincroniza los controles con la config del backend al arrancar. */
  async function cargarConfig() {
    try {
      const res = await fetch("/api/config");
      const cfg = await res.json();
      const g = cfg.gemelo || cfg; // compatibilidad con formato plano
      ctlCab.value = g.cab;
      elCabVal.textContent = g.cab;
      ctlCw.value = g.cw;
      elCwVal.textContent = Number(g.cw).toFixed(3);
      ctlN.value = g.n;
      elNVal.textContent = Number(g.n).toFixed(1);
      selModo.querySelectorAll("button").forEach((b) =>
        b.classList.toggle("activo", b.dataset.modo === cfg.modo));
      btnEstres.classList.toggle("encendido", cfg.estres);
      btnEstres.textContent = cfg.estres ? "Activado" : "Desactivado";
    } catch (err) {
      console.warn("No se pudo cargar /api/config:", err);
    }
  }

  function pintarTabla(msg) {
    const errores = (msg.comparacion && msg.comparacion.error_por_canal) || {};
    elTabla.innerHTML = msg.orden_canales.map((c) => {
      const wl = msg.longitudes_onda[c];
      const etiqueta = LONGITUD_TXT[c] || `${wl} nm`;
      const pred = msg.prediccion ? msg.prediccion[c] : "—";
      const err = errores[c] !== undefined ? errores[c] : "—";
      return `<div class="canal">
        <div class="nombre">${c}</div>
        <div class="longitud">${etiqueta}</div>
        <div class="valor">${msg.canales[c]}</div>
        <div class="pred">gemelo: ${pred} · Δ ${err}</div>
      </div>`;
    }).join("");
  }

  function pintarComparacion(msg) {
    if (!msg.comparacion) return;
    elRmse.textContent = msg.comparacion.rmse;
    elRmseRel.textContent = `${(msg.comparacion.rmse_rel * 100).toFixed(1)} %`;
    elSesgo.textContent = msg.comparacion.sesgo;
    const hayAnomalia = !!msg.anomalia;
    elAlerta.classList.toggle("oculto", !hayAnomalia);
    elTarjetaComp.classList.toggle("alerta-fondo", hayAnomalia);
    if (msg.gemelo) {
      elIndice.textContent = `${msg.gemelo.indice_clorofila} / 100`;
      elBarra.style.width = `${msg.gemelo.indice_clorofila}%`;
      elModo.textContent = msg.gemelo.modo || "—";
      elGemeloCab.textContent = msg.gemelo.cab;
    }
    if (msg.hoja) {
      elHojaCab.textContent = msg.hoja.cab_verdadero ?? msg.hoja.cab_base;
    }
    // ML: null en transmitancia o sin modelo -> "no disponible".
    elMlCab.textContent = (msg.cab_estimado_ml === null ||
      msg.cab_estimado_ml === undefined)
      ? "no disponible"
      : `${msg.cab_estimado_ml} µg/cm²`;
  }

  function pintarMensaje(msg) {
    contador += 1;
    elContador.textContent = contador;
    elUltima.textContent = new Date(msg.timestamp).toLocaleTimeString();
    actualizarGrafico(msg);
    pintarTabla(msg);
    pintarComparacion(msg);
  }

  /** Sondeo REST como reserva cuando no hay WebSocket (Vercel serverless). */
  function iniciarSondeo() {
    if (temporizadorSondeo) return;
    transporte = "sondeo";
    const elTransporte = document.getElementById("transporte");
    if (elTransporte) elTransporte.textContent = "sondeo 2 s";
    setEstado("Conectado (sondeo)", "conectado");
    const sondear = async () => {
      try {
        const res = await fetch("/api/lectura");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        pintarMensaje(await res.json());
      } catch (err) {
        console.warn("Fallo de sondeo:", err);
      }
    };
    sondear();
    temporizadorSondeo = setInterval(sondear, INTERVALO_SONDEO);
  }
  function conectar() {
    // Mismo host/puerto que sirve la pagina; funciona en local y en red.
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/ws`;
    const ws = new WebSocket(url);

    // Si el WebSocket no abre (p. ej. Vercel serverless, sin WS),
    // se pasa a sondeo REST en vez de reintentar para siempre.
    clearTimeout(temporizadorEsperaWs);
    temporizadorEsperaWs = setTimeout(() => {
      if (transporte === "websocket" && contador === 0) {
        try { ws.close(); } catch (_) { /* ya cerrado */ }
        const fallos = (conectar.fallos = (conectar.fallos || 0) + 1);
        if (fallos >= 2) {
          iniciarSondeo();
        } else {
          temporizadorReconexion = setTimeout(conectar, 2000);
        }
      }
    }, 5000);

    ws.onopen = () => {
      conectar.fallos = 0;
      clearTimeout(temporizadorEsperaWs);
      setEstado("Conectado", "conectado");
      if (temporizadorReconexion) {
        clearTimeout(temporizadorReconexion);
        temporizadorReconexion = null;
      }
    };

    ws.onmessage = (ev) => pintarMensaje(JSON.parse(ev.data));

    ws.onclose = () => {
      if (transporte !== "sondeo" && contador > 0) {
        setEstado("Reintentando…", "reintentando");
        // Reconexion automatica con espera de 2 s.
        temporizadorReconexion = setTimeout(conectar, 2000);
      }
    };

    ws.onerror = () => ws.close();
  }

  setEstado("Desconectado", "desconectado");
  cargarConfig();
  conectar();
})();
