import express, { json, urlencoded } from 'express';
import cors from 'cors';
import { config as _config } from 'dotenv';
import transferPortalRoutes from './routes/transfer_portal_tracker';
import { info, warn, error as _error } from './config/logger';
import { getConfig } from './utils/env-validator';

// Load environment variables
_config();

// Validate environment variables and get config
const config = getConfig();

const app = express();

// CORS configuration
const corsOptions = {
  origin: config.nodeEnv === 'production' ? ['https://xii-os.com', 'https://api.xii-os.com'] : '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
  maxAge: 86400, // 24 hours
};

// Middleware
app.use(cors(corsOptions));
app.use(json());
app.use(urlencoded({ extended: true }));

// Request logging middleware
app.use((req, res, next) => {
  info(`${req.method} ${req.url}`, {
    ip: req.ip,
    userAgent: req.get('user-agent'),
  });
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    environment: config.nodeEnv,
  });
});

// Routes
app.use('/api/transfer-portal-tracker', transferPortalRoutes);

// 404 handler
app.use((req, res) => {
  warn(`Route not found: ${req.method} ${req.url}`);
  res.status(404).json({ error: 'Not Found' });
});

// Error handling middleware
// eslint-disable-next-line @typescript-eslint/no-unused-vars
app.use((err, req, res, _next) => {
  _error('Unhandled error:', err);

  // Don't expose internal error details in production
  const response = {
    error: config.nodeEnv === 'production' ? 'Internal Server Error' : err.message,
  };

  if (config.nodeEnv !== 'production') {
    response.stack = err.stack;
  }

  res.status(err.status || 500).json(response);
});

// Graceful shutdown
const shutdown = async () => {
  info('Shutting down server...');
  try {
    await server.close();
    info('Server stopped');
    info('Database connections closed');
    process.exit(0);
  } catch (error) {
    _error('Error during shutdown:', error);
    process.exit(1);
  }
};

// Start server
const server = app.listen(config.port, () => {
  info(`Server is running on port ${config.port} in ${config.nodeEnv} mode`);
});

// Handle shutdown signals
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
