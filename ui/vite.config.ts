import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tailwindcss(), tsConfigPaths()],
  server: { port: 3000, host: true },
  preview: {
    port: 3000,
    host: true,
    allowedHosts: [
      "13.220.135.187",
      "ec2-13-220-135-187.compute-1.amazonaws.com",
      ".compute-1.amazonaws.com",
    ],
  },
});
