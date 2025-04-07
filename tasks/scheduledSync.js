/**
 * Scheduled Notion Sync Task
 * 
 * This task runs on a schedule to sync data between Notion and XII-OS.
 */

const cron = require('node-cron');
const NotionModel = require('../models/notion');
const NotionService = require('../services/notionService');
const knex = require('../../../db/knex');
const winston = require('winston');

// Initialize logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  defaultMeta: { service: 'notion-sync-task' },
  transports: [
    new winston.transports.File({ filename: 'logs/notion-error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/notion-combined.log' }),
    new winston.transports.Console({ format: winston.format.simple() })
  ],
});

// Configure sync tables for each integration
const DEFAULT_SYNC_CONFIG = {
  'MBB Transfer Portal': {
    tables: ['players'],
    filters: { sport: 'basketball' }
  }
};

/**
 * Perform sync from Notion to XII-OS
 */
async function syncFromNotion() {
  try {
    logger.info('Starting scheduled sync FROM Notion...');
    
    // Get all active integrations
    const integrations = await knex('notion_integrations')
      .where({ active: true })
      .select('*');
    
    for (const integration of integrations) {
      logger.info(`Processing integration: ${integration.name}`);
      
      // Start a new transaction for each integration
      const trx = await knex.transaction();
      
      try {
        // Parse settings
        const settings = typeof integration.settings === 'string' 
          ? JSON.parse(integration.settings) 
          : integration.settings || {};
          
        // Get database ID
        const databaseId = settings.default_database_id;
        if (!databaseId) {
          logger.warn(`No database ID found for integration ${integration.name}, skipping`);
          await trx.commit(); // No changes to commit, but clean up transaction
          continue;
        }
        
        // Initialize Notion service
        const notionService = new NotionService({ token: integration.token });
        
        try {
          // Get records from Notion
          const records = await notionService.queryDatabase(databaseId);
          const formattedRecords = notionService.mapRecordsToStandardFormat(records);
          
          // Determine target table
          const syncConfig = DEFAULT_SYNC_CONFIG[integration.name] || {};
          const tables = syncConfig.tables || settings.target_tables || ['players'];
          
          // For each target table, prepare and save data
          for (const table of tables) {
            // Prepare data for database insertion
            const dataToInsert = formattedRecords.map(record => {
              return {
                notion_id: record.id,
                ...record.properties,
                created_at: new Date(record.created_time),
                updated_at: new Date(record.last_edited_time)
              };
            });
            
            // Insert into specified table using the transaction
            if (dataToInsert.length > 0) {
              // Clear existing records with same notion_ids to avoid duplicates
              const notionIds = dataToInsert.map(record => record.notion_id);
              
              // Only delete if the table has a notion_id column
              const tableInfo = await trx.table(table).columnInfo();
              if (tableInfo.notion_id) {
                await trx(table).whereIn('notion_id', notionIds).del();
              }
              
              // Insert the records
              const result = await trx(table).insert(dataToInsert).returning('id');
              logger.info(`Synced ${result.length} records from Notion to ${table} for ${integration.name}`);
            } else {
              logger.info(`No records to sync from Notion to ${table} for ${integration.name}`);
            }
          }
          
          // Update last sync timestamp
          await trx('notion_integrations')
            .where({ id: integration.id })
            .update({ 
              last_sync: new Date(),
              updated_at: new Date()
            });
            
          // Commit the transaction
          await trx.commit();
          logger.info(`Successfully synced data for integration ${integration.name}`);
        } catch (apiError) {
          // Rollback on API error
          await trx.rollback();
          logger.error(`API error syncing data for integration ${integration.name}:`, apiError);
        }
      } catch (dbError) {
        // Rollback on database error
        await trx.rollback();
        logger.error(`Database error processing integration ${integration.name}:`, dbError);
      }
    }
    
    logger.info('Completed scheduled sync FROM Notion');
  } catch (error) {
    logger.error('Error during scheduled sync FROM Notion:', error);
  }
}

/**
 * Initialize scheduled tasks
 */
function initScheduledTasks() {
  // Schedule sync from Notion every hour
  cron.schedule('0 * * * *', async () => {
    try {
      await syncFromNotion();
    } catch (error) {
      logger.error('Unhandled error in scheduled task:', error);
    }
  });
  
  logger.info('Notion sync tasks scheduled');
  
  // Run initial sync after startup (with delay)
  setTimeout(async () => {
    try {
      await syncFromNotion();
    } catch (error) {
      logger.error('Unhandled error in initial sync:', error);
    }
  }, 60000);
}

module.exports = {
  initScheduledTasks,
  syncFromNotion
}; 