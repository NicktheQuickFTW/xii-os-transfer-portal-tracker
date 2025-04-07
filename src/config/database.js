import knex from 'knex';
import logger from './logger';

const dbConfig = {
  client: 'pg',
  connection: {
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
    ssl: false,
  },
  pool: {
    min: 2,
    max: 10,
    createTimeoutMillis: 3000,
    acquireTimeoutMillis: 30000,
    idleTimeoutMillis: 30000,
    reapIntervalMillis: 1000,
    createRetryIntervalMillis: 100,
    propagateCreateError: false,
  },
};

const db = knex(dbConfig);

// Test database connection
db.raw('SELECT 1')
  .then(() => {
    logger.info('Database connection established successfully');
  })
  .catch(error => {
    logger.error('Database connection failed:', error);
    process.exit(1);
  });

export default db;
