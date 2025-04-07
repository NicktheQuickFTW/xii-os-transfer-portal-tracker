import axios from 'axios';
import cheerio from 'cheerio';
import { logger } from '../utils/logger.js';
import db from '../config/database.js';

class TransferPortalTrackerService {
  constructor() {
    this.baseUrl =
      'https://www.on3.com/transfer-portal-tracker/wire/basketball/';
    this.topPlayersUrl =
      'https://www.on3.com/transfer-portal-tracker/industry/basketball/';
    this.headers = {
      'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
      Accept:
        'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'sec-ch-ua': '"Not A;Brand";v="99", "Chromium";v="121"',
      'sec-ch-ua-mobile': '?0',
      'sec-ch-ua-platform': '"Windows"',
    };

    try {
      // Initialize service
      this.init();
      logger.info('Transfer portal tracker service initialized successfully');
    } catch (error) {
      logger.error(
        'Failed to initialize transfer portal tracker service:',
        error
      );
      throw error;
    }
  }

  async init() {
    try {
      // Test the connection
      await axios.get(this.baseUrl, { headers: this.headers });
    } catch (error) {
      logger.error(
        'Failed to initialize transfer portal tracker service:',
        error
      );
      throw error;
    }
  }

  async fetchData() {
    try {
      logger.info('Fetching transfer portal tracker data...');

      // Fetch main transfer portal tracker page
      const response = await axios.get(this.baseUrl, { headers: this.headers });
      const html = response.data;

      // Parse the data
      const $ = cheerio.load(html);
      const players = await this._extractPlayersFromPage(html);

      return {
        last_updated: new Date().toISOString(),
        players: players,
      };
    } catch (error) {
      logger.error('Error fetching data:', error);
      throw error;
    }
  }

  async _extractPlayersFromPage(html) {
    const $ = cheerio.load(html);
    const players = [];

    $('.transfer-portal-tracker-card').each((i, card) => {
      try {
        const $card = $(card);

        // Extract basic info
        const name = $card.find('.player-name').text().trim();
        const detailsText = $card.find('.player-details').text().trim();

        // Parse details
        const details = detailsText.split('•').map(d => d.trim());
        const position = details[0] || null;
        const height = details[1] || null;
        const classYear = details[2] || null;

        // Extract school info
        const previousSchool =
          $card.find('.player-school').text().trim() || null;

        // Extract stats
        const statsText = $card.find('.player-stats').text().trim();
        const stats = this._parseStats(statsText);

        // Extract profile URL
        const profileUrl = $card.find('a').attr('href') || null;

        // Create player object
        const player = {
          name,
          position,
          height,
          class_year: classYear,
          previous_school: previousSchool,
          stats,
          profile_url: profileUrl,
          transfer_date: new Date().toISOString(),
          status: 'in portal',
          destination_school: null,
        };

        players.push(player);
      } catch (error) {
        logger.error(`Error extracting player ${i}:`, error);
      }
    });

    return players;
  }

  _parseStats(statsText) {
    const stats = {};
    const parts = statsText.split('/');

    parts.forEach(part => {
      const [value, label] = part.trim().split(' ');
      if (value && label) {
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
          stats[label.toLowerCase()] = numValue;
        }
      }
    });

    return stats;
  }

  _parseRanking(rankingText) {
    const match = rankingText.match(/#(\d+)/);
    return match ? parseInt(match[1]) : null;
  }

  _mergePlayerLists(mainList, topList) {
    const playerMap = new Map(mainList.map(p => [p.name, p]));

    topList.forEach(topPlayer => {
      if (playerMap.has(topPlayer.name)) {
        // Update existing player with new information
        const existingPlayer = playerMap.get(topPlayer.name);
        Object.assign(existingPlayer, topPlayer);
      } else {
        // Add new player
        playerMap.set(topPlayer.name, topPlayer);
      }
    });

    return Array.from(playerMap.values());
  }

  async getAllPlayers() {
    try {
      return await db('transfer_portal')
        .select('*')
        .orderBy('updated_at', 'desc');
    } catch (error) {
      logger.error('Error fetching all players:', error);
      throw new Error('Failed to fetch players');
    }
  }

  async searchPlayers(query) {
    try {
      return await db('transfer_portal')
        .select('*')
        .where('name', 'ilike', `%${query}%`)
        .orWhere('position', 'ilike', `%${query}%`)
        .orWhere('previous_team', 'ilike', `%${query}%`)
        .orderBy('updated_at', 'desc');
    } catch (error) {
      logger.error('Error searching players:', error);
      throw new Error('Failed to search players');
    }
  }

  async getStats() {
    try {
      const [summary, statusDist, positionDist, eligibilityDist] =
        await Promise.all([
          db('transfer_portal')
            .select(
              db.raw('COUNT(*) as total_transfers'),
              db.raw(
                "COUNT(CASE WHEN status = 'Available' THEN 1 END) as available_transfers"
              ),
              db.raw(
                "COUNT(CASE WHEN status = 'Committed' THEN 1 END) as committed_transfers"
              ),
              db.raw(
                "COUNT(CASE WHEN status = 'Withdrawn' THEN 1 END) as withdrawn_transfers"
              )
            )
            .first(),
          this._getDistribution('status'),
          this._getDistribution('position'),
          this._getDistribution('eligibility'),
        ]);

      const averageStats = await this._getAverageStats();
      const topPerformers = await this._getTopPerformers();
      const recentActivity = await this._getRecentActivity();

      return {
        summary,
        distributions: {
          status: statusDist,
          position: positionDist,
          eligibility: eligibilityDist,
        },
        averageStats,
        topPerformers,
        recentActivity,
      };
    } catch (error) {
      logger.error('Error getting stats:', error);
      throw new Error('Failed to get stats');
    }
  }

  async getTrendingTransfers() {
    try {
      return await db('transfer_portal')
        .select('*')
        .where('updated_at', '>', db.raw("now() - interval '7 days'"))
        .orderBy('updated_at', 'desc')
        .limit(10);
    } catch (error) {
      logger.error('Error fetching trending transfers:', error);
      throw new Error('Failed to fetch trending transfers');
    }
  }

  async comparePlayers(player1Id, player2Id) {
    try {
      const players = await db('transfer_portal')
        .select('*')
        .whereIn('id', [player1Id, player2Id]);

      if (players.length !== 2) {
        throw new Error('One or both players not found');
      }

      return {
        players,
        comparison: this._calculateComparison(players[0], players[1]),
      };
    } catch (error) {
      logger.error('Error comparing players:', error);
      throw new Error('Failed to compare players');
    }
  }

  async getTeamAnalysis(teamId) {
    try {
      const [teamStats, transfers] = await Promise.all([
        db('transfer_portal')
          .select(
            db.raw('COUNT(*) as total_transfers'),
            db.raw(
              "COUNT(CASE WHEN status = 'Available' THEN 1 END) as available_transfers"
            ),
            db.raw(
              "COUNT(CASE WHEN status = 'Committed' THEN 1 END) as committed_transfers"
            )
          )
          .where('previous_team_id', teamId)
          .first(),
        db('transfer_portal')
          .select('*')
          .where('previous_team_id', teamId)
          .orderBy('entry_date', 'desc'),
      ]);

      return {
        teamStats,
        transfers,
        analysis: this._analyzeTeamTransfers(transfers),
      };
    } catch (error) {
      logger.error('Error analyzing team transfers:', error);
      throw new Error('Failed to analyze team transfers');
    }
  }

  async getTransferPredictions(playerId) {
    try {
      const player = await db('transfer_portal')
        .select('*')
        .where('id', playerId)
        .first();

      if (!player) {
        throw new Error('Player not found');
      }

      const similarPlayers = await this._findSimilarPlayers(player);
      const predictions = this._generatePredictions(player, similarPlayers);

      return {
        player,
        similarPlayers,
        predictions,
      };
    } catch (error) {
      logger.error('Error generating transfer predictions:', error);
      throw new Error('Failed to generate predictions');
    }
  }

  // Private helper methods
  async _getDistribution(field) {
    return db('transfer_portal')
      .select(field)
      .count('* as count')
      .groupBy(field)
      .orderBy('count', 'desc');
  }

  async _getAverageStats() {
    return db('transfer_portal')
      .select(
        db.raw("AVG((stats->>'points_per_game')::float) as avg_ppg"),
        db.raw("AVG((stats->>'rebounds_per_game')::float) as avg_rpg"),
        db.raw("AVG((stats->>'assists_per_game')::float) as avg_apg")
      )
      .where('status', 'Available')
      .first();
  }

  async _getTopPerformers() {
    return db('transfer_portal')
      .select('*')
      .whereNotNull('stats')
      .orderBy(db.raw("(stats->>'points_per_game')::float"), 'desc')
      .limit(10);
  }

  async _getRecentActivity() {
    return db('transfer_portal')
      .select('*')
      .where('updated_at', '>', db.raw("now() - interval '30 days'"))
      .orderBy('updated_at', 'desc')
      .limit(10);
  }

  _calculateComparison(player1, player2) {
    const stats1 = player1.stats || {};
    const stats2 = player2.stats || {};

    return {
      scoring: this._compareStats(
        stats1.points_per_game,
        stats2.points_per_game
      ),
      rebounds: this._compareStats(
        stats1.rebounds_per_game,
        stats2.rebounds_per_game
      ),
      assists: this._compareStats(
        stats1.assists_per_game,
        stats2.assists_per_game
      ),
      efficiency: this._compareStats(
        stats1.field_goal_percentage,
        stats2.field_goal_percentage
      ),
    };
  }

  _compareStats(stat1, stat2) {
    if (!stat1 || !stat2) return null;
    return {
      difference: parseFloat(stat1) - parseFloat(stat2),
      percentage: (parseFloat(stat1) / parseFloat(stat2)) * 100 - 100,
    };
  }

  _analyzeTeamTransfers(transfers) {
    const positionBreakdown = {};
    const eligibilityBreakdown = {};

    transfers.forEach(transfer => {
      positionBreakdown[transfer.position] =
        (positionBreakdown[transfer.position] || 0) + 1;
      eligibilityBreakdown[transfer.eligibility] =
        (eligibilityBreakdown[transfer.eligibility] || 0) + 1;
    });

    return {
      positionBreakdown,
      eligibilityBreakdown,
      trends: this._analyzeTrends(transfers),
    };
  }

  _analyzeTrends(transfers) {
    const monthlyTransfers = {};
    transfers.forEach(transfer => {
      const month = new Date(transfer.entry_date).toLocaleString('default', {
        month: 'long',
      });
      monthlyTransfers[month] = (monthlyTransfers[month] || 0) + 1;
    });

    return {
      monthlyTransfers,
      peakMonth: Object.entries(monthlyTransfers).reduce((a, b) =>
        b[1] > a[1] ? b : a
      )[0],
    };
  }

  async _findSimilarPlayers(player) {
    return db('transfer_portal')
      .select('*')
      .where('position', player.position)
      .whereNot('id', player.id)
      .orderBy(
        db.raw("ABS((stats->>'points_per_game')::float - ?)", [
          player.stats.points_per_game,
        ])
      )
      .limit(5);
  }

  _generatePredictions(player, similarPlayers) {
    const predictions = {
      likely_destinations: [],
      success_probability: 0,
      fit_analysis: {},
    };

    // Implementation of prediction logic would go here
    // This would involve machine learning models or statistical analysis

    return predictions;
  }
}

const transferPortalTracker = new TransferPortalTrackerService();
export default transferPortalTracker;
