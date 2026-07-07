import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY;

// In local/demo mode (no Supabase project wired up yet) this stays null and
// every page falls back to the bundled snapshot in src/data/demoSnapshot.json,
// which was produced by running parsers/*.py and optimizer/optimize.py on the
// real FSA, VC and daily-report files for this project.
export const supabase = url && key ? createClient(url, key) : null;
