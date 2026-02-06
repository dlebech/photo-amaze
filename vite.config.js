import { defineConfig } from 'vite';
import { resolve } from 'path';
import { viteStaticCopy } from 'vite-plugin-static-copy';

export default defineConfig({
  plugins: [
    viteStaticCopy({
      targets: [
        {
          src: 'static/js/src/libs/*.js',
          dest: 'libs',
        },
      ],
    }),
  ],
  build: {
    rollupOptions: {
      input: {
        photoamaze: resolve(__dirname, 'static/js/src/photoamaze.js'),
        site: resolve(__dirname, 'static/js/src/site.js'),
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name][extname]',
      },
    },
    outDir: 'static/js/dist',
    emptyOutDir: true,
    sourcemap: true,
  },
  css: {
    preprocessorOptions: {
      less: {},
    },
  },
});
