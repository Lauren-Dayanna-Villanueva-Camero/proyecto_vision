import { useState } from "react";
import { View, Text, TextInput, Button, Image, ActivityIndicator, ScrollView, StyleSheet, Alert } from "react-native";
import * as ImagePicker from "expo-image-picker";

// IP del PC donde corre server.py (la muestra el servidor al iniciar).
// También se puede cambiar desde la app, en el campo "Servidor".
const SERVIDOR_INICIAL = "http://192.168.20.45:5000";
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
  const [servidor, setServidor] = useState(SERVIDOR_INICIAL);
  const [uri, setUri] = useState(null);
  const [b64, setB64] = useState(null);
  const [origen, setOrigen] = useState("celular"); // de dónde salió la imagen: cámara o galería
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);

  const procesar = (res, origenImagen) => {
    if (res.canceled) return;
    const asset = res.assets[0];
    setUri(asset.uri);
    setB64(asset.base64); // la imagen ya viene convertida a Base64
    setOrigen(origenImagen);
    setResultado(null);
  };

  const abrirCamara = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return Alert.alert("Se necesita permiso de cámara");
    procesar(await ImagePicker.launchCameraAsync({ base64: true, quality: 0.5 }), "celular_camara");
  };

  const abrirGaleria = async () => {
    procesar(await ImagePicker.launchImageLibraryAsync({ base64: true, quality: 0.5 }), "celular_galeria");
  };

  const enviar = async () => {
    setCargando(true);
    setResultado(null);
    try {
      const res = await fetch(`${servidor.trim()}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: "cliente_movil_001",
          timestamp: new Date().toISOString(),
          camera_id: origen,
          location: "Móvil",
          image: b64,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error del servidor");
      setResultado(data);
    } catch (e) {
      Alert.alert("Error", `${e.message}\n\nRevisa la IP del servidor y que el celular esté en la misma red WiFi.`);
    } finally {
      setCargando(false);
    }
  };

  const accion = resultado ? decidirAccion(resultado) : null;

  return (
    <ScrollView contentContainerStyle={s.container}>
      <Text style={s.titulo}>Gato o perro</Text>

      <Text style={s.etiqueta}>Servidor</Text>
      <TextInput
        style={s.input}
        value={servidor}
        onChangeText={setServidor}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
      />

      <View style={s.fila}>
        <Button title="Cámara" onPress={abrirCamara} />
        <Button title="Galería" onPress={abrirGaleria} />
      </View>

      {uri && <Image source={{ uri }} style={s.img} />}
      {uri && <Button title="Predecir" onPress={enviar} disabled={cargando} />}
      {cargando && <ActivityIndicator size="large" style={{ marginTop: 16 }} />}

      {resultado && (
        <Text style={s.resultado}>
          {resultado.prediction} ({(resultado.confidence * 100).toFixed(1)} %)
        </Text>
      )}
      {accion && (
        <View style={[s.accion, { backgroundColor: accion.color }]}>
          <Text style={s.accionTitulo}>Acción: {accion.titulo}</Text>
          <Text style={s.accionTexto}>{accion.mensaje}</Text>
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flexGrow: 1, alignItems: "center", justifyContent: "center", padding: 20 },
  titulo: { fontSize: 28, fontWeight: "bold", marginBottom: 20 },
  etiqueta: { alignSelf: "stretch", fontSize: 13, color: "#555" },
  input: { alignSelf: "stretch", borderWidth: 1, borderColor: "#bbb", borderRadius: 6, padding: 8, marginBottom: 20 },
  fila: { flexDirection: "row", gap: 20, marginBottom: 20 },
  img: { width: 250, height: 250, borderRadius: 8, marginVertical: 16 },
  resultado: { fontSize: 24, marginTop: 20, fontWeight: "bold" },
  accion: { alignSelf: "stretch", borderRadius: 8, padding: 14, marginTop: 12 },
  accionTitulo: { color: "white", fontWeight: "bold", fontSize: 16, textAlign: "center" },
  accionTexto: { color: "white", textAlign: "center", marginTop: 4 },
});
