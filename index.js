/**
 * Notion Integration Module
 * 
 * This module provides functionality for integrating with Notion workspaces,
 * allowing bidirectional data sync between XII-OS and Notion.
 */

const routes = require('./routes');
const NotionService = require('./services/notionService');
const scheduledTasks = require('./tasks/scheduledSync');

// Initialize scheduled tasks if enabled
if (process.env.ENABLE_NOTION_SCHEDULED_SYNC !== 'false') {
  scheduledTasks.initScheduledTasks();
}

module.exports = {
  routes,
  models: {
    Notion: require('./models/notion')
  },
  services: {
    NotionService
  },
  tasks: scheduledTasks
}; 