import { useEffect, useRef, useState } from "react";

// Usa el mismo host desde el que abres la página, así funciona también desde otros dispositivos
const API_URL = `http://${window.location.hostname}:5000/predict`;
const UMBRAL_CONFIANZA = 0.8; // por debajo de esto no se toma ninguna decisión

// Lógica de negocio del cliente: puerta para mascotas que solo deja entrar gatos
function decidirAccion(respuesta) {
  const porcentaje = (respuesta.confidence * 100).toFixed(0);
  if (respuesta.confidence < UMBRAL_CONFIANZA) {
    return { titulo: "Revisar", color: "#b7791f", mensaje: `No estoy seguro (${respuesta.prediction}, ${porcentaje} %). La puerta sigue cerrada.` };
  }
  if (respuesta.prediction === "gato") {
    return { titulo: "Abrir puerta", color: "#2f855a", mensaje: `Es un gato (${porcentaje} %). Se abre la puerta.` };
  }
  return { titulo: "Alarma", color: "#c53030", mensaje: `Es un perro (${porcentaje} %). Puerta cerrada y se activa la alarma.` };
}

export default function App() {
  // Metadatos que acompañan a la imagen
  const [clientId, setClientId] = useState("cliente_web_001");
  const [cameraId, setCameraId] = useState("web_upload");
  const [location, setLocation] = useState("Navegador");

  const [preview, setPreview] = useState(null); // imagen como "data:image/...;base64,...."
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  const [camaraActiva, setCamaraActiva] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const nuevaImagen = (dataUrl, origen) => {
    setPreview(dataUrl);
    setResultado(null);
    setError(null);
    // Si no has escrito un ID de cámara propio, se pone el del origen de la imagen
    setCameraId((actual) => (["web_upload", "webcam_navegador"].includes(actual) ? origen : actual));
  };

  // --- Captura 1: desde un archivo ---
  const onFile = (e) => {
    const file = e.target.files[0];
    // Se vacía el selector para que, si eliges el mismo archivo otra vez, se vuelva a cargar
    e.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setPreview(null);
      setResultado(null);
      setError(`"${file.name}" no es una imagen. Elige un archivo JPG, PNG, WEBP...`);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => nuevaImagen(reader.result, "web_upload");
    reader.readAsDataURL(file); // imagen binaria -> Base64
  };

  // --- Captura 2: desde la cámara del dispositivo ---
  const abrirCamara = async () => {
    setError(null);
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({ video: true });
      setCamaraActiva(true);
    } catch {
      setError("No se pudo abrir la cámara. El navegador solo la permite en http://localhost o en páginas https.");
    }
  };

  const cerrarCamara = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCamaraActiva(false);
  };

  const tomarFoto = () => {
    const video = videoRef.current;
    // Si el video todavía no muestra imagen, la foto saldría vacía (0x0 píxeles)
    if (!video || !video.videoWidth) {
      setError("La cámara todavía está cargando. Espera un momento y vuelve a intentarlo.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    nuevaImagen(canvas.toDataURL("image/jpeg", 0.9), "webcam_navegador"); // fotograma -> JPG en Base64
    cerrarCamara();
  };

  // Conecta el video con la cámara cuando se enciende, y la apaga al salir de la página
  useEffect(() => {
    if (camaraActiva && videoRef.current) videoRef.current.srcObject = streamRef.current;
  }, [camaraActiva]);
  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), []);

  // --- Envío del JSON al servicio web ---
  const enviar = async () => {
    setCargando(true);
    setError(null);
    setResultado(null);
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          timestamp: new Date().toISOString(),
          camera_id: cameraId,
          location: location,
          image: preview.split(",")[1], // quita el prefijo "data:image/...;base64,"
        }),
      });
      // Si en el puerto 5000 responde otro programa, la respuesta no es JSON
      const data = await res.json().catch(() => null);
      if (!data) throw new Error(`El servidor respondió ${res.status} pero no envió un JSON. ¿Es la dirección correcta?`);
      if (!res.ok) throw new Error(data.error || "Error del servidor");
      setResultado(data);
    } catch (err) {
      setError(err instanceof TypeError ? "No se pudo conectar con el servidor. ¿Está corriendo server.py?" : err.message);
    } finally {
      setCargando(false);
    }
  };

  const accion = resultado ? decidirAccion(resultado) : null;
  const campo = { display: "flex", flexDirection: "column", textAlign: "left", fontSize: 14, gap: 4, flex: 1, minWidth: 130 };
  const entrada = { padding: 6, fontSize: 14 };
  const boton = { padding: "8px 20px", fontSize: 16, cursor: "pointer" };

  return (
    <div style={{ maxWidth: 520, margin: "40px auto", padding: "0 16px", fontFamily: "sans-serif", textAlign: "center" }}>
      <h1>Gato o perro</h1>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20 }}>
        <label style={campo}>
          ID del cliente
          <input style={entrada} value={clientId} onChange={(e) => setClientId(e.target.value)} />
        </label>
        <label style={campo}>
          ID de la cámara
          <input style={entrada} value={cameraId} onChange={(e) => setCameraId(e.target.value)} />
        </label>
        <label style={campo}>
          Ubicación
          <input style={entrada} value={location} onChange={(e) => setLocation(e.target.value)} />
        </label>
      </div>

      <div style={{ display: "flex", gap: 12, justifyContent: "center", alignItems: "center", flexWrap: "wrap" }}>
        <input type="file" accept="image/*" onChange={onFile} />
        {!camaraActiva && <button style={boton} onClick={abrirCamara}>Usar cámara</button>}
      </div>

      {camaraActiva && (
        <div style={{ marginTop: 20 }}>
          <video ref={videoRef} autoPlay playsInline muted style={{ maxWidth: "100%", borderRadius: 8 }} />
          <br />
          <button style={boton} onClick={tomarFoto}>Tomar foto</button>{" "}
          <button style={boton} onClick={cerrarCamara}>Cancelar</button>
        </div>
      )}

      {preview && !camaraActiva && (
        <div style={{ marginTop: 20 }}>
          <img src={preview} alt="vista previa" style={{ maxWidth: "100%", borderRadius: 8 }} />
          <br />
          <button style={{ ...boton, marginTop: 12 }} onClick={enviar} disabled={cargando}>
            {cargando ? "Analizando..." : "Predecir"}
          </button>
        </div>
      )}

      {resultado && (
        <div style={{ marginTop: 20 }}>
          <h2 style={{ margin: 0 }}>
            {resultado.prediction} ({(resultado.confidence * 100).toFixed(1)} %)
          </h2>
          <div style={{ marginTop: 12, padding: 14, borderRadius: 8, color: "white", background: accion.color }}>
            <strong>Acción: {accion.titulo}</strong>
            <br />
            {accion.mensaje}
          </div>
          <p style={{ fontSize: 13, opacity: 0.8 }}>
            Consulta {resultado.request_id} · {resultado.stored ? "imagen guardada en GridFS" : "sin almacenamiento (MongoDB apagado)"}
          </p>
        </div>
      )}
      {error && <p style={{ color: "crimson" }}>{error}</p>}
    </div>
  );
}
