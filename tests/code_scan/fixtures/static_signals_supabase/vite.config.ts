export default {
  define: {
    __API__: JSON.stringify(import.meta.env.VITE_SUPABASE_URL)
  }
}
