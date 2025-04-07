import { Router } from 'express';
import knex from '../../db/utils/db';
import { supabase } from '../config/supabase';
import { requireAuth, requireRole, roles } from '../middleware/auth';
import { transferPortalService } from '../services/transferPortalTracker';
import { logger } from '../utils/logger';

const router = Router();

// Validate database connection
const validateDbConnection = async () => {
  try {
    await knex.raw('SELECT 1');
    return true;
  } catch (error) {
    logger.error('Database connection error:', {
      message: error.message,
      code: error.code,
      detail: error.detail,
    });
    return false;
  }
};

// Error handler middleware
const errorHandler = (error, _req, res) => {
  logger.error('Transfer portal error:', {
    message: error.message,
    code: error.code,
    detail: error.detail,
    stack: error.stack,
  });

  if (error.code === 'ECONNREFUSED') {
    return res.status(503).json({
      error: 'Database connection failed',
      details: 'Unable to connect to the database. Please try again later.',
    });
  }

  if (error.code === '42P01') {
    return res.status(500).json({
      error: 'Database schema error',
      details: 'Required tables are missing. Please ensure migrations have been run.',
    });
  }

  if (error.code === '28P01') {
    return res.status(500).json({
      error: 'Authentication failed',
      details: 'Database credentials are invalid.',
    });
  }

  if (error.code === '28000') {
    return res.status(500).json({
      error: 'SSL connection required',
      details: 'A secure SSL connection is required for the database.',
    });
  }

  if (error.code === 'ETIMEDOUT') {
    return res.status(503).json({
      error: 'Connection timeout',
      details: 'The database connection timed out. Please try again.',
    });
  }

  res.status(500).json({
    error: 'Internal server error',
    message: error.message,
    code: error.code,
  });
};

// Connection check middleware with retry
const checkDbConnection = async (req, res, next) => {
  let retries = 3;
  let connected = false;

  while (retries > 0 && !connected) {
    connected = await validateDbConnection();
    if (!connected) {
      retries--;
      if (retries > 0) {
        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second before retrying
      }
    }
  }

  if (!connected) {
    return res.status(503).json({
      error: 'Service unavailable',
      details: 'Database connection is not available after multiple attempts',
    });
  }
  next();
};

// Apply middleware to all routes
router.use(checkDbConnection);

/**
 * GET /api/transfer-portal-tracker
 * Get all transfer portal tracker entries with optional filters
 * Public endpoint - no auth required
 */
router.get('/', async (req, res) => {
  try {
    const {
      status,
      position,
      eligibility,
      transfer_type,
      min_ppg,
      min_rpg,
      min_apg,
      sort_by,
      sort_order = 'desc',
      page = 1,
      limit = 25,
    } = req.query;

    // Validate numeric parameters
    const validatedPage = Math.max(1, parseInt(page) || 1);
    const validatedLimit = Math.min(100, Math.max(1, parseInt(limit) || 25));

    let query = knex('transfer_portal').select('*');

    // Validate and apply filters
    if (status && ['Available', 'Committed', 'Withdrawn'].includes(status)) {
      query.where('status', status);
    }

    if (position && ['PG', 'SG', 'SF', 'PF', 'C'].includes(position)) {
      query.where('position', position);
    }

    if (eligibility) query.where('eligibility', eligibility);
    if (transfer_type) query.where('transfer_type', transfer_type);

    // Validate numeric filters
    if (min_ppg && !isNaN(min_ppg)) {
      // eslint-disable-next-line quotes
      query.whereRaw("(stats->>'points_per_game')::float >= ?", [parseFloat(min_ppg)]);
    }
    if (min_rpg && !isNaN(min_rpg)) {
      // eslint-disable-next-line quotes
      query.whereRaw("(stats->>'rebounds_per_game')::float >= ?", [parseFloat(min_rpg)]);
    }
    if (min_apg && !isNaN(min_apg)) {
      // eslint-disable-next-line quotes
      query.whereRaw("(stats->>'assists_per_game')::float >= ?", [parseFloat(min_apg)]);
    }

    // Validate and apply sorting
    const validSortFields = ['entry_date', 'updated_at', 'status', 'position'];
    const validSortOrders = ['asc', 'desc'];

    if (sort_by) {
      if (sort_by.startsWith('stats.')) {
        const statField = sort_by.split('.')[1];
        const validStatFields = ['points_per_game', 'rebounds_per_game', 'assists_per_game'];
        if (validStatFields.includes(statField)) {
          query.orderByRaw(
            `(stats->>'${statField}')::float ${validSortOrders.includes(sort_order) ? sort_order : 'desc'}`
          );
        }
      } else if (validSortFields.includes(sort_by)) {
        query.orderBy(sort_by, validSortOrders.includes(sort_order) ? sort_order : 'desc');
      }
    } else {
      query.orderBy('entry_date', 'desc');
    }

    // Apply pagination
    const offset = (validatedPage - 1) * validatedLimit;
    query.offset(offset).limit(validatedLimit);

    // Execute query with timeout
    const [results, total] = await Promise.all([
      query.timeout(5000),
      knex('transfer_portal').count('id').first().timeout(5000),
    ]);

    if (!results || !total) {
      throw new Error('Failed to fetch transfer portal data');
    }

    res.json({
      data: results,
      pagination: {
        current_page: validatedPage,
        total_pages: Math.ceil(parseInt(total.count) / validatedLimit),
        total_entries: parseInt(total.count),
        per_page: validatedLimit,
      },
    });
  } catch (error) {
    logger.error('Transfer portal tracker error:', {
      message: error.message,
      stack: error.stack,
    });
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/transfer-portal-tracker/stats
 * Get transfer portal tracker statistics
 */
router.get('/stats', async (req, res) => {
  try {
    const stats = await transferPortalService.getStats();
    res.json(stats);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/transfer-portal-tracker/trending
 * Get trending transfers
 */
router.get('/trending', async (req, res) => {
  try {
    const trending = await transferPortalService.getTrendingTransfers();
    res.json(trending);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/transfer-portal-tracker/search
 * Search for players
 */
router.get('/search', async (req, res) => {
  try {
    const { query, position, status, eligibility } = req.query;

    const baseQuery = knex('transfer_portal').select('*');

    // Apply filters
    if (query) {
      baseQuery.where(function () {
        this.where('position', 'ilike', `%${query}%`)
          .orWhere('eligibility', 'ilike', `%${query}%`)
          .orWhere('hometown', 'ilike', `%${query}%`)
          .orWhere('high_school', 'ilike', `%${query}%`);
      });
    }

    if (position) {
      baseQuery.where('position', position);
    }

    if (status) {
      baseQuery.where('status', status);
    }

    if (eligibility) {
      baseQuery.where('eligibility', eligibility);
    }

    const results = await baseQuery.orderBy('entry_date', 'desc').limit(25);

    res.json(results);
  } catch (error) {
    logger.error('Error searching transfers:', {
      message: error.message,
      code: error.code,
      detail: error.detail,
      stack: error.stack,
    });
    res.status(500).json({
      error: 'Internal server error',
      details: error.message,
      code: error.code,
    });
  }
});

/**
 * GET /api/transfer-portal-tracker/compare
 * Compare players
 */
router.get('/compare', async (req, res) => {
  try {
    const { player1Id, player2Id } = req.query;
    const comparison = await transferPortalService.comparePlayers(player1Id, player2Id);
    res.json(comparison);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/transfer-portal-tracker/team-analysis
 * Get team analysis
 */
router.get('/team-analysis', async (req, res) => {
  try {
    const { teamId } = req.query;
    const analysis = await transferPortalService.getTeamAnalysis(teamId);
    res.json(analysis);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/transfer-portal-tracker/predictions
 * Get transfer predictions
 */
router.get('/predictions', async (req, res) => {
  try {
    const { playerId } = req.query;
    const predictions = await transferPortalService.getTransferPredictions(playerId);
    res.json(predictions);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /api/transfer-portal-tracker/watchlist
 * Add a player to user's watchlist
 * Requires authentication
 */
router.post('/watchlist/:playerId', requireAuth, async (req, res) => {
  try {
    const { playerId } = req.params;
    const userId = req.user.id;

    // First verify the player exists using Knex
    const player = await knex('transfer_portal').where('id', playerId).first();

    if (!player) {
      return res.status(404).json({ error: 'Player not found' });
    }

    // Add to watchlist using Supabase
    const { data, error } = await supabase.from('watchlist').upsert([
      {
        user_id: userId,
        player_id: playerId,
        created_at: new Date().toISOString(),
      },
    ]);

    if (error) throw error;

    res.json({ message: 'Player added to watchlist', data });
  } catch (error) {
    logger.error('Watchlist error:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/transfer-portal-tracker/watchlist
 * Get user's watchlist
 * Requires authentication
 */
router.get('/watchlist', requireAuth, async (req, res) => {
  try {
    const userId = req.user.id;

    // Get watchlist entries using Supabase
    const { data: watchlist, error } = await supabase
      .from('watchlist')
      .select('player_id')
      .eq('user_id', userId);

    if (error) throw error;

    // Get detailed player info using Knex
    if (watchlist.length > 0) {
      const playerIds = watchlist.map(item => item.player_id);
      const players = await knex('transfer_portal').whereIn('id', playerIds);
      res.json({ data: players });
    } else {
      res.json({ data: [] });
    }
  } catch (error) {
    logger.error('Watchlist error:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /api/transfer-portal-tracker
 * Create a new transfer portal entry
 * Requires scout or admin role
 */
router.post('/', requireAuth, requireRole([roles.SCOUT, roles.ADMIN]), async (req, res) => {
  try {
    const newPlayer = req.body;

    // Create player using Knex transaction
    const [playerId] = await knex('transfer_portal').insert(newPlayer).returning('id');

    // Broadcast real-time update using Supabase
    const { error: broadcastError } = await supabase
      .from('transfer_portal')
      .insert([{ ...newPlayer, id: playerId }]);

    if (broadcastError) {
      logger.error('Broadcast error:', broadcastError);
    }

    res.status(201).json({
      message: 'Player added successfully',
      data: { id: playerId, ...newPlayer },
    });
  } catch (error) {
    logger.error('Create player error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Apply error handler
router.use(errorHandler);

export default router;
