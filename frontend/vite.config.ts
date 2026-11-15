import { defineConfig, type ProxyOptions } from "vite";
const localProxy: ProxyOptions = {
  target: "http://127.0.0.1:8787",
  changeOrigin: true,
  configure(proxy) {
    proxy.on("proxyReq", (out, req) => {
      if (req.headers.origin === "http://127.0.0.1:5173")
        out.setHeader("Origin", "http://127.0.0.1:8787");
    });
  },
};
export default defineConfig({
  base: "/ui/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": localProxy, "/assets": localProxy },
  },
  build: { outDir: "dist", assetsDir: "bundles" },
});
