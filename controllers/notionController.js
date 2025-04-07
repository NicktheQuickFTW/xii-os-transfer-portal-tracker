/**
 * Notion Controller
 * 
 * Handles API requests related to Notion integration.
 */

const NotionService = require('../services/notionService');
const NotionModel = require('../models/notion');
const knex = require('../../../db/knex');
const winston = require('winston');

// Initialize logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  defaultMeta: { service: 'notion-controller' },
  transports: [
    new winston.transports.File({ filename: 'logs/notion-error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/notion-combined.log' }),
    new winston.transports.Console({ format: winston.format.simple() })
  ],
});

// Get all Notion integrations
exports.getAllIntegrations = async (req, res) => {
  try {
    const integrations = await NotionModel.findAll();
    res.status(200).json({
      success: true,
      count: integrations.length,
      data: integrations
    });
  } catch (error) {
    logger.error('Error fetching integrations:', error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// Get a single integration
exports.getIntegration = async (req, res) => {
  try {
    const integration = await NotionModel.findById(req.params.id);
    
    if (!integration) {
      return res.status(404).json({
        success: false,
        error: 'Integration not found'
      });
    }
    
    res.status(200).json({
      success: true,
      data: integration
    });
  } catch (error) {
    logger.error(`Error fetching integration ${req.params.id}:`, error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// Create a new integration
exports.createIntegration = async (req, res) => {
  try {
    const { name, token, workspace_id, description } = req.body;
    
    if (!name || !token || !workspace_id) {
      return res.status(400).json({
        success: false,
        error: 'Please provide name, token, and workspace_id'
      });
    }
    
    // Check if integration exists already
    const existingIntegration = await NotionModel.findByWorkspaceId(workspace_id);
    if (existingIntegration) {
      return res.status(400).json({
        success: false,
        error: 'Integration with this workspace ID already exists'
      });
    }
    
    // Test the token by initializing the service
    try {
      const notionService = new NotionService({ token });
      await notionService.listDatabases();
    } catch (error) {
      logger.error('Invalid Notion token:', error);
      return res.status(400).json({
        success: false,
        error: 'Invalid Notion token'
      });
    }
    
    const integrationData = {
      name,
      token,
      workspace_id,
      description,
      created_at: new Date(),
      updated_at: new Date()
    };
    
    const result = await NotionModel.create(integrationData);
    const newIntegration = result[0];
    
    // Don't return the token in the response
    delete newIntegration.token;
    
    res.status(201).json({
      success: true,
      data: newIntegration
    });
  } catch (error) {
    logger.error('Error creating integration:', error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// Update integration
exports.updateIntegration = async (req, res) => {
  try {
    const { name, token, description } = req.body;
    
    // Find current integration
    const integration = await NotionModel.findById(req.params.id);
    if (!integration) {
      return res.status(404).json({
        success: false,
        error: 'Integration not found'
      });
    }
    
    // Test new token if provided
    if (token) {
      try {
        const notionService = new NotionService({ token });
        await notionService.listDatabases();
      } catch (error) {
        logger.error('Invalid Notion token:', error);
        return res.status(400).json({
          success: false,
          error: 'Invalid Notion token'
        });
      }
    }
    
    const updateData = {};
    if (name) updateData.name = name;
    if (token) updateData.token = token;
    if (description) updateData.description = description;
    updateData.updated_at = new Date();
    
    const result = await NotionModel.update(req.params.id, updateData);
    const updatedIntegration = result[0];
    
    // Don't return the token in the response
    delete updatedIntegration.token;
    
    res.status(200).json({
      success: true,
      data: updatedIntegration
    });
  } catch (error) {
    logger.error(`Error updating integration ${req.params.id}:`, error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// Delete integration
exports.deleteIntegration = async (req, res) => {
  try {
    const integration = await NotionModel.findById(req.params.id);
    
    if (!integration) {
      return res.status(404).json({
        success: false,
        error: 'Integration not found'
      });
    }
    
    await NotionModel.remove(req.params.id);
    
    res.status(200).json({
      success: true,
      data: {}
    });
  } catch (error) {
    logger.error(`Error deleting integration ${req.params.id}:`, error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// List Notion databases
exports.listDatabases = async (req, res) => {
  try {
    const integration = await NotionModel.findById(req.params.id);
    
    if (!integration) {
      return res.status(404).json({
        success: false,
        error: 'Integration not found'
      });
    }
    
    const notionService = new NotionService({ token: integration.token });
    const databases = await notionService.listDatabases();
    
    res.status(200).json({
      success: true,
      count: databases.length,
      data: databases.map(db => ({
        id: db.id,
        title: db.title.map(t => t.plain_text).join(''),
        created_time: db.created_time,
        last_edited_time: db.last_edited_time
      }))
    });
  } catch (error) {
    logger.error(`Error listing databases for integration ${req.params.id}:`, error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// Query Notion database
exports.queryDatabase = async (req, res) => {
  try {
    const { integration_id, database_id } = req.params;
    const filter = req.body.filter || {};
    
    const integration = await NotionModel.findById(integration_id);
    
    if (!integration) {
      return res.status(404).json({
        success: false,
        error: 'Integration not found'
      });
    }
    
    const notionService = new NotionService({ token: integration.token });
    const records = await notionService.queryDatabase(database_id, filter);
    
    // Transform records to a more usable format
    const formattedRecords = notionService.mapRecordsToStandardFormat(records);
    
    res.status(200).json({
      success: true,
      count: formattedRecords.length,
      data: formattedRecords
    });
  } catch (error) {
    logger.error(`Error querying database for integration ${req.params.integration_id}:`, error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// Sync data from Notion to XII-OS
exports.syncFromNotion = async (req, res) => {
  // Use a transaction for database operations
  const trx = await knex.transaction();
  
  try {
    const { integration_id, database_id } = req.params;
    const { target_table } = req.body;
    
    if (!target_table) {
      await trx.rollback();
      return res.status(400).json({
        success: false,
        error: 'Please provide target_table'
      });
    }
    
    const integration = await trx('notion_integrations')
      .where({ id: integration_id })
      .first();
    
    if (!integration) {
      await trx.rollback();
      return res.status(404).json({
        success: false,
        error: 'Integration not found'
      });
    }
    
    const notionService = new NotionService({ token: integration.token });
    const records = await notionService.queryDatabase(database_id);
    
    // Transform records to a standardized format
    const formattedRecords = notionService.mapRecordsToStandardFormat(records);
    
    // Prepare data for database insertion
    const dataToInsert = formattedRecords.map(record => {
      return {
        notion_id: record.id,
        ...record.properties,
        created_at: new Date(record.created_time),
        updated_at: new Date(record.last_edited_time)
      };
    });
    
    // Check if table exists and has necessary columns
    const hasTable = await trx.schema.hasTable(target_table);
    if (!hasTable) {
      await trx.rollback();
      return res.status(400).json({
        success: false,
        error: `Table ${target_table} does not exist`
      });
    }
    
    // Get list of Notion IDs
    const notionIds = dataToInsert.map(record => record.notion_id);
    
    // Clear existing records with same notion_ids to avoid duplicates
    const tableInfo = await trx.table(target_table).columnInfo();
    if (tableInfo.notion_id) {
      await trx(target_table).whereIn('notion_id', notionIds).del();
    }
    
    // Insert into specified table
    let result = [];
    if (dataToInsert.length > 0) {
      result = await trx(target_table).insert(dataToInsert).returning('*');
    }
    
    // Update last sync timestamp
    await trx('notion_integrations')
      .where({ id: integration_id })
      .update({ 
        last_sync: new Date(),
        updated_at: new Date()
      });
    
    // Commit the transaction
    await trx.commit();
    
    res.status(200).json({
      success: true,
      count: result.length,
      message: `Successfully synced ${result.length} records from Notion to ${target_table}`,
      data: result
    });
  } catch (error) {
    // Rollback the transaction
    await trx.rollback();
    
    logger.error(`Error syncing from Notion to XII-OS for integration ${req.params.integration_id}:`, error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
};

// Sync data from XII-OS to Notion
exports.syncToNotion = async (req, res) => {
  try {
    const { integration_id, database_id } = req.params;
    const { source_table, filters } = req.body;
    
    if (!source_table) {
      return res.status(400).json({
        success: false,
        error: 'Please provide source_table'
      });
    }
    
    const integration = await NotionModel.findById(integration_id);
    
    if (!integration) {
      return res.status(404).json({
        success: false,
        error: 'Integration not found'
      });
    }
    
    // Get data from XII-OS database with a transaction to ensure connection is released
    const trx = await knex.transaction();
    let sourceData;
    
    try {
      // Check if table exists
      const hasTable = await trx.schema.hasTable(source_table);
      if (!hasTable) {
        await trx.rollback();
        return res.status(400).json({
          success: false,
          error: `Table ${source_table} does not exist`
        });
      }
      
      // Get data with filters
      sourceData = await trx(source_table)
        .where(filters || {})
        .select('*');
      
      await trx.commit();
    } catch (dbError) {
      await trx.rollback();
      logger.error(`Database error retrieving data from ${source_table}:`, dbError);
      return res.status(500).json({
        success: false,
        error: `Error retrieving data from ${source_table}`
      });
    }
    
    const notionService = new NotionService({ token: integration.token });
    
    // Get database schema to format properties correctly
    const schema = await notionService.getDatabaseSchema(database_id);
    
    // Create pages in Notion with rate limiting to avoid overloading Notion API
    const createdPages = [];
    for (const item of sourceData) {
      try {
        const properties = notionService.convertToNotionProperties(item, schema);
        const page = await notionService.createPage(database_id, properties);
        createdPages.push(page);
        
        // Add a small delay to avoid rate limits
        await new Promise(resolve => setTimeout(resolve, 250));
      } catch (pageError) {
        logger.error(`Error creating Notion page for item ${JSON.stringify(item.id)}:`, pageError);
        // Continue with the next item
      }
    }
    
    // Update the integration's last sync timestamp
    const updateTrx = await knex.transaction();
    try {
      await updateTrx('notion_integrations')
        .where({ id: integration_id })
        .update({ 
          last_sync: new Date(),
          updated_at: new Date()
        });
      
      await updateTrx.commit();
    } catch (updateError) {
      await updateTrx.rollback();
      logger.error(`Error updating last_sync timestamp:`, updateError);
    }
    
    res.status(200).json({
      success: true,
      count: createdPages.length,
      message: `Successfully synced ${createdPages.length} records from ${source_table} to Notion`,
      data: createdPages
    });
  } catch (error) {
    logger.error(`Error syncing from XII-OS to Notion for integration ${req.params.integration_id}:`, error);
    res.status(500).json({
      success: false,
      error: 'Server Error'
    });
  }
}; 