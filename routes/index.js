/**
 * Notion Integration Routes
 */

const express = require('express');
const router = express.Router();
const notionController = require('../controllers/notionController');

// Integration management routes
router.get('/integrations', notionController.getAllIntegrations);
router.get('/integrations/:id', notionController.getIntegration);
router.post('/integrations', notionController.createIntegration);
router.put('/integrations/:id', notionController.updateIntegration);
router.delete('/integrations/:id', notionController.deleteIntegration);

// Database interaction routes
router.get('/integrations/:id/databases', notionController.listDatabases);
router.post('/integrations/:integration_id/databases/:database_id/query', notionController.queryDatabase);

// Sync routes
router.post('/integrations/:integration_id/databases/:database_id/sync-from-notion', notionController.syncFromNotion);
router.post('/integrations/:integration_id/databases/:database_id/sync-to-notion', notionController.syncToNotion);

module.exports = router; 