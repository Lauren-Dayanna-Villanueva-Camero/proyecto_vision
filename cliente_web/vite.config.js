import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // host: true -> la página también se puede abrir desde otro equipo de la red
  // (por ejemplo http://192.168.x.x:5173), no solo desde localhost
  server: { host: true },
})
