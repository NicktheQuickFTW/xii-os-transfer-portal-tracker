/**
 * Notion Integration Model
 * 
 * This model handles the database operations for Notion integration.
 */

const knex = require('../../../db/knex');

const TABLE_NAME = 'notion_integrations';

/**
 * Find all Notion integrations
 * @returns {Promise<Array>} Array of integration objects
 */
function findAll() {
  return knex(TABLE_NAME).select('*');
}

/**
 * Find Notion integration by ID
 * @param {number} id - Integration ID
 * @returns {Promise<Object>} Integration object
 */
function findById(id) {
  return knex(TABLE_NAME).where({ id }).first();
}

/**
 * Find Notion integration by workspace ID
 * @param {string} workspaceId - Notion workspace ID
 * @returns {Promise<Object>} Integration object
 */
function findByWorkspaceId(workspaceId) {
  return knex(TABLE_NAME).where({ workspace_id: workspaceId }).first();
}

/**
 * Create a new Notion integration
 * @param {Object} integration - Integration data
 * @returns {Promise<Array>} Array containing the ID of the new integration
 */
function create(integration) {
  return knex(TABLE_NAME).insert(integration).returning('*');
}

/**
 * Update a Notion integration
 * @param {number} id - Integration ID
 * @param {Object} integration - Updated integration data
 * @returns {Promise<number>} Number of rows updated
 */
function update(id, integration) {
  return knex(TABLE_NAME).where({ id }).update(integration).returning('*');
}

/**
 * Delete a Notion integration
 * @param {number} id - Integration ID
 * @returns {Promise<number>} Number of rows deleted
 */
function remove(id) {
  return knex(TABLE_NAME).where({ id }).del();
}

/**
 * Save Notion data to a specific table
 * @param {string} tableName - Table to save data to
 * @param {Array|Object} data - Data to save
 * @returns {Promise<Array>} Array of inserted records
 */
async function saveDataToTable(tableName, data) {
  if (Array.isArray(data)) {
    return knex(tableName).insert(data).returning('*');
  } else {
    return knex(tableName).insert([data]).returning('*');
  }
}

/**
 * Get data from a specific table
 * @param {string} tableName - Table to get data from
 * @param {Object} filters - Optional filters
 * @returns {Promise<Array>} Array of records
 */
function getDataFromTable(tableName, filters = {}) {
  return knex(tableName).where(filters).select('*');
}

module.exports = {
  findAll,
  findById,
  findByWorkspaceId,
  create,
  update,
  remove,
  saveDataToTable,
  getDataFromTable
}; 