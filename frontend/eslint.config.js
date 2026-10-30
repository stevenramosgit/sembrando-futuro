// Revisión de estilo y complejidad ciclomática de la PWA (documentos 22 y 23): máximo 10 caminos por función.
export default [
  {
    files: ["src/**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
    rules: {
      complexity: ["error", 10],
      "no-unused-vars": ["error", { ignoreRestSiblings: true }], // se permite separar campos con {a, ...resto}
    },
  },
];
