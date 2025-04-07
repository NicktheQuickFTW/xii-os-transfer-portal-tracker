import { createClient } from '@supabase/supabase-js';
import logger from './logger.js';

// Initialize Supabase client
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_ANON_KEY,
  {
    auth: {
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: true,
    },
    realtime: {
      params: {
        eventsPerSecond: 10,
      },
    },
  }
);

// Test Supabase connection
const testConnection = async () => {
  try {
    const { data, error } = await supabase
      .from('transfer_portal')
      .select('id')
      .limit(1);
    if (error) throw error;
    logger.info('Supabase connection established successfully');
  } catch (error) {
    logger.error('Supabase connection failed:', error);
  }
};

testConnection();

export default supabase;
