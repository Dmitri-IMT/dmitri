export default [
  {
    ignores: ["node_modules/", "dist/", "build/"],
  },
  {
    rules: {
      // Aqui você pode adicionar regras futuras. 
      // Deixando vazio por enquanto, a pipeline vai apenas checar 
      // a sintaxe básica.
      // "no-console": "warn",
      // "no-unused-vars": "error"
    }
  }
];