import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/ollama": {
        target: "http://127.0.0.1:11434",
        changeOrigin: true,
        rewrite: path => path.replace(/^\/ollama/, ""),
      },
      "/comfy": {
        target: "http://127.0.0.1:8199",
        changeOrigin: true,
        ws: true,
        rewrite: path => path.replace(/^\/comfy/, ""),
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ""),
      },
    },
  },
})
