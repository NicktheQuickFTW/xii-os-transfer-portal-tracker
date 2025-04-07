/**
 * Notion API Service
 * 
 * This service handles API interactions with Notion.
 */

const { Client } = require('@notionhq/client');
const winston = require('winston');

// Initialize logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  defaultMeta: { service: 'notion-service' },
  transports: [
    new winston.transports.File({ filename: 'logs/notion-error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/notion-combined.log' }),
    new winston.transports.Console({ format: winston.format.simple() })
  ],
});

/**
 * NotionService class for handling Notion API operations
 */
class NotionService {
  /**
   * Constructor
   * @param {Object} config - Configuration object with Notion API token
   */
  constructor(config) {
    this.token = config.token;
    this.notion = new Client({ auth: config.token });
    logger.info('Notion service initialized');
  }

  /**
   * Get a list of databases from the workspace
   * @returns {Promise<Array>} List of databases
   */
  async listDatabases() {
    try {
      const response = await this.notion.search({
        filter: {
          value: 'database',
          property: 'object'
        }
      });
      logger.info(`Retrieved ${response.results.length} databases`);
      return response.results;
    } catch (error) {
      logger.error('Error listing databases:', error);
      throw error;
    }
  }

  /**
   * Query a database
   * @param {string} databaseId - Notion database ID
   * @param {Object} options - Query options including filter criteria and page size
   * @returns {Promise<Array>} Database query results
   */
  async queryDatabase(databaseId, options = {}) {
    try {
      const response = await this.notion.databases.query({
        database_id: databaseId,
        page_size: options.page_size || 100,
        filter: {
          and: []  // Empty filter to match all records
        }
      });
      logger.info(`Retrieved ${response.results.length} records from database ${databaseId}`);
      return response.results;
    } catch (error) {
      logger.error(`Error querying database ${databaseId}:`, error);
      throw error;
    }
  }

  /**
   * Create a page in a database
   * @param {string} databaseId - Notion database ID
   * @param {Object} properties - Page properties
   * @returns {Promise<Object>} Created page
   */
  async createPage(databaseId, properties) {
    try {
      const response = await this.notion.pages.create({
        parent: { database_id: databaseId },
        properties: properties
      });
      logger.info(`Created page in database ${databaseId}`);
      return response;
    } catch (error) {
      logger.error(`Error creating page in database ${databaseId}:`, error);
      throw error;
    }
  }

  /**
   * Update a page
   * @param {string} pageId - Notion page ID
   * @param {Object} properties - Updated properties
   * @returns {Promise<Object>} Updated page
   */
  async updatePage(pageId, properties) {
    try {
      const response = await this.notion.pages.update({
        page_id: pageId,
        properties: properties
      });
      logger.info(`Updated page ${pageId}`);
      return response;
    } catch (error) {
      logger.error(`Error updating page ${pageId}:`, error);
      throw error;
    }
  }

  /**
   * Get database schema
   * @param {string} databaseId - Notion database ID
   * @returns {Promise<Object>} Database schema
   */
  async getDatabaseSchema(databaseId) {
    try {
      const response = await this.notion.databases.retrieve({ database_id: databaseId });
      logger.info(`Retrieved schema for database ${databaseId}`);
      return response.properties;
    } catch (error) {
      logger.error(`Error retrieving schema for database ${databaseId}:`, error);
      throw error;
    }
  }

  /**
   * Map database records to a standardized format
   * @param {Array} records - Notion database records
   * @returns {Array} Standardized records
   */
  mapRecordsToStandardFormat(records) {
    return records.map(record => {
      const result = {
        id: record.id,
        created_time: record.created_time,
        last_edited_time: record.last_edited_time,
        properties: {}
      };

      // Process each property based on its type
      Object.entries(record.properties).forEach(([key, property]) => {
        switch (property.type) {
          case 'title':
            result.properties[key] = property.title.map(item => item.plain_text).join('');
            break;
          case 'rich_text':
            result.properties[key] = property.rich_text.map(item => item.plain_text).join('');
            break;
          case 'number':
            result.properties[key] = property.number;
            break;
          case 'select':
            result.properties[key] = property.select?.name || null;
            break;
          case 'multi_select':
            result.properties[key] = property.multi_select.map(item => item.name);
            break;
          case 'date':
            result.properties[key] = property.date?.start || null;
            break;
          case 'checkbox':
            result.properties[key] = property.checkbox;
            break;
          case 'url':
            result.properties[key] = property.url;
            break;
          case 'email':
            result.properties[key] = property.email;
            break;
          case 'phone_number':
            result.properties[key] = property.phone_number;
            break;
          case 'formula':
            if (property.formula.type === 'string') {
              result.properties[key] = property.formula.string;
            } else if (property.formula.type === 'number') {
              result.properties[key] = property.formula.number;
            } else if (property.formula.type === 'boolean') {
              result.properties[key] = property.formula.boolean;
            } else if (property.formula.type === 'date') {
              result.properties[key] = property.formula.date?.start || null;
            }
            break;
          default:
            result.properties[key] = null;
        }
      });

      return result;
    });
  }

  /**
   * Convert XII-OS data to Notion property format
   * @param {Object} data - Data to convert
   * @param {Object} schema - Notion database schema
   * @returns {Object} Notion-formatted properties
   */
  convertToNotionProperties(data, schema) {
    const properties = {};

    Object.entries(data).forEach(([key, value]) => {
      if (!schema[key]) return;

      const propertyType = schema[key].type;
      
      switch (propertyType) {
        case 'title':
          properties[key] = {
            title: [{ type: 'text', text: { content: String(value) } }]
          };
          break;
        case 'rich_text':
          properties[key] = {
            rich_text: [{ type: 'text', text: { content: String(value) } }]
          };
          break;
        case 'number':
          properties[key] = { number: Number(value) };
          break;
        case 'select':
          properties[key] = { select: { name: String(value) } };
          break;
        case 'multi_select':
          const selections = Array.isArray(value) ? value : [value];
          properties[key] = {
            multi_select: selections.map(item => ({ name: String(item) }))
          };
          break;
        case 'date':
          properties[key] = { date: { start: value } };
          break;
        case 'checkbox':
          properties[key] = { checkbox: Boolean(value) };
          break;
        case 'url':
          properties[key] = { url: String(value) };
          break;
        case 'email':
          properties[key] = { email: String(value) };
          break;
        case 'phone_number':
          properties[key] = { phone_number: String(value) };
          break;
      }
    });

    return properties;
  }
}

module.exports = NotionService; 