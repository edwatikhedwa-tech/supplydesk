import { createClient, type Session, type User } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;

export function mapSupabaseUser(user: User) {
  const displayName = user.user_metadata?.full_name ?? user.user_metadata?.name ?? user.email ?? 'Пользователь';
  return {
    email: user.email ?? '',
    display_name: displayName,
    workspace_name: user.user_metadata?.workspace_name ?? 'SupplyDesk',
  };
}

export function getSupabaseSessionToken(session: Session | null) {
  return session?.access_token ?? '';
}

export async function getSupabaseAccessToken() {
  if (!supabase) return '';
  const { data } = await supabase.auth.getSession();
  return getSupabaseSessionToken(data.session);
}
