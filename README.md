# Notion Integration Module

This module provides functionality for integrating Notion databases with XII-OS, allowing bidirectional data synchronization between platforms.

## Features

- Connect to Notion workspaces via Integration tokens
- List and browse Notion databases
- Query Notion database content
- Sync data from Notion to XII-OS
- Push XII-OS data to Notion databases
- Maintain persistent connections to Notion teamspaces

## Setup Instructions

1. **Create a Notion Integration**:
   - Go to [Notion Developers](https://www.notion.com/my-integrations)
   - Create a new integration for your workspace
   - Set appropriate capabilities (Read Content, Update Content, etc.)
   - Copy the integration token

2. **Share Databases with the Integration**:
   - In Notion, open the database you want to connect
   - Click "Share" in the top-right
   - Use the "@" symbol to invite your integration
   - Grant appropriate permissions

3. **Add Integration to XII-OS**:
   - Use the XII-OS API to create a new integration record
   - Provide the integration token
   - Test the connection

## API Endpoints

### Integration Management

- `GET /api/notion/integrations` - List all Notion integrations
- `GET /api/notion/integrations/:id` - Get specific integration
- `POST /api/notion/integrations` - Add new integration
- `PUT /api/notion/integrations/:id` - Update integration
- `DELETE /api/notion/integrations/:id` - Delete integration

### Database Operations

- `GET /api/notion/integrations/:id/databases` - List databases in workspace
- `POST /api/notion/integrations/:integration_id/databases/:database_id/query` - Query database

### Synchronization

- `POST /api/notion/integrations/:integration_id/databases/:database_id/sync-from-notion` - Pull data from Notion to XII-OS
- `POST /api/notion/integrations/:integration_id/databases/:database_id/sync-to-notion` - Push data from XII-OS to Notion

## Examples

### Creating a New Integration

```javascript
fetch('/api/notion/integrations', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Big 12 Transfer Portal',
    token: 'secret_abcdefghijklmnopqrstuvwxyz123456',
    workspace_id: 'your-workspace-id',
    description: 'Integration for managing transfer portal data'
  })
})
```

### Syncing Data from Notion

```javascript
fetch('/api/notion/integrations/1/databases/abc123def456/sync-from-notion', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    target_table: 'players'
  })
})
```

### Pushing Data to Notion

```javascript
fetch('/api/notion/integrations/1/databases/abc123def456/sync-to-notion', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    source_table: 'players',
    filters: { team: 'Texas' }
  })
})
```

## Database Schema

The module creates a `notion_integrations` table with the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | integer | Primary key |
| name | string | Name of the integration |
| token | text | Notion API token (encrypted) |
| workspace_id | string | Notion workspace ID |
| description | text | Optional description |
| active | boolean | Whether integration is active |
| settings | jsonb | Additional settings |
| last_sync | timestamp | Last synchronization time |
| created_at | timestamp | Creation timestamp |
| updated_at | timestamp | Last update timestamp |

## Security Considerations

- Notion tokens are stored securely in the database
- All API requests are authenticated
- Token validation occurs before any operations
- Proper error handling prevents sensitive information exposure 