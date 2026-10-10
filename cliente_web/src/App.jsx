import { useState } from "react";

// Usa el mismo host desde el que abres la página, así funciona también desde otros dispositivos
const API_URL = `http://${window.location.hostname}:5000/predict`;

export default function App() {
  const [preview, setPreview] = useState(null);
  const [b64, setB64] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  const onFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setPreview(reader.result);
      setB64(reader.result.split(",")[1]); // quita el prefijo "data:image/...;base64,"
      setResultado(null);
      setError(null);
    };
    reader.readAsDataURL(file);
  };

  const enviar = async () => {
    setCargando(true);
    setError(null);
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: "cliente_web_001",
          timestamp: new Date().toISOString(),
          camera_id: "web_upload",
          location: "Navegador",
          image: b64,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error del servidor");
      setResultado(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ maxWidth: 480, margin: "40px auto", fontFamily: "sans-serif", textAlign: "center" }}>
      <h1>Gato o perro</h1>
      <input type="file" accept="image/*" onChange={onFile} />

      {preview && (
        <div style={{ marginTop: 20 }}>
          <img src={preview} alt="vista previa" style={{ maxWidth: "100%", borderRadius: 8 }} />
          <br />
          <button onClick={enviar} disabled={cargando} style={{ marginTop: 12, padding: "8px 20px" }}>
            {cargando ? "Analizando..." : "Predecir"}
          </button>
        </div>
      )}

      {resultado && (
        <h2 style={{ marginTop: 20 }}>
          {resultado.prediction} ({(resultado.confidence * 100).toFixed(1)} %)
        </h2>
      )}
      {error && <p style={{ color: "crimson" }}>{error}</p>}
    </div>
  );
}