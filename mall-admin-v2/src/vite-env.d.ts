/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BASE_API: string
  readonly VITE_SERVER_ORIGIN: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
