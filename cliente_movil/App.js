import { useState } from "react";
import { View, Text, Button, Image, ActivityIndicator, StyleSheet, Alert } from "react-native";
import * as ImagePicker from "expo-image-picker";

// CAMBIA ESTA IP por la de tu PC (o la de tu servidor si no estás en la misma red)
const API_URL = "http://192.168.20.45:5000/predict";

export default function App() {
  const [uri, setUri] = useState(null);
  const [b64, setB64] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);

  const procesar = (res) => {
    if (res.canceled) return;
    const asset = res.assets[0];
    setUri(asset.uri);
    setB64(asset.base64);
    setResultado(null);
  };

  const abrirCamara = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return Alert.alert("Se necesita permiso de cámara");
    procesar(await ImagePicker.launchCameraAsync({ base64: true, quality: 0.5 }));
  };

  const abrirGaleria = async () => {
    procesar(await ImagePicker.launchImageLibraryAsync({ base64: true, quality: 0.5 }));
  };

  const enviar = async () => {
    setCargando(true);
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: "cliente_movil_001",
          timestamp: new Date().toISOString(),
          camera_id: "celular",
          location: "Móvil",
          image: b64,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error del servidor");
      setResultado(data);
    } catch (e) {
      Alert.alert("Error", e.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <View style={s.container}>
      <Text style={s.titulo}>Gato o perro</Text>
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
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20 },
  titulo: { fontSize: 28, fontWeight: "bold", marginBottom: 20 },
  fila: { flexDirection: "row", gap: 20, marginBottom: 20 },
  img: { width: 250, height: 250, borderRadius: 8, marginVertical: 16 },
  resultado: { fontSize: 24, marginTop: 20, fontWeight: "bold" },
});