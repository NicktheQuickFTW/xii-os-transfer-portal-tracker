import logger from '../config/logger.js';

class EnvironmentValidator {
  constructor() {
    this.requiredVars = new Set([
      'PORT',
      'NODE_ENV',
      'DB_HOST',
      'DB_PORT',
      'DB_USER',
      'DB_PASSWORD',
      'DB_NAME',
    ]);

    this.optionalVars = new Set([
      'DB_CA_CERT',
      'LOG_LEVEL',
      'CACHE_EXPIRY',
      'USE_247SPORTS',
      'USE_ON3',
      'USE_RIVALS',
      'ON3_API_KEY',
      'RIVALS_API_KEY',
      '247SPORTS_API_KEY',
    ]);
  }

  validate() {
    const missing = [];
    const invalid = [];

    // Check required variables
    for (const varName of this.requiredVars) {
      const value = process.env[varName];
      if (!value) {
        missing.push(varName);
      }
    }

    // Validate specific variables
    if (process.env.PORT && isNaN(process.env.PORT)) {
      invalid.push('PORT must be a number');
    }

    if (process.env.DB_PORT && isNaN(process.env.DB_PORT)) {
      invalid.push('DB_PORT must be a number');
    }

    if (process.env.CACHE_EXPIRY && isNaN(process.env.CACHE_EXPIRY)) {
      invalid.push('CACHE_EXPIRY must be a number');
    }

    const validNodeEnvs = ['development', 'production', 'test'];
    if (process.env.NODE_ENV && !validNodeEnvs.includes(process.env.NODE_ENV)) {
      invalid.push(`NODE_ENV must be one of: ${validNodeEnvs.join(', ')}`);
    }

    // Log warnings for missing optional variables that might be needed
    for (const varName of this.optionalVars) {
      if (!process.env[varName]) {
        logger.warn(`Optional environment variable ${varName} is not set`);
      }
    }

    // Handle validation results
    if (missing.length > 0 || invalid.length > 0) {
      const errors = [];

      if (missing.length > 0) {
        errors.push(`Missing required environment variables: ${missing.join(', ')}`);
      }

      if (invalid.length > 0) {
        errors.push(`Invalid environment variables: ${invalid.join(', ')}`);
      }

      const errorMessage = errors.join('\n');
      logger.error(errorMessage);
      throw new Error(errorMessage);
    }

    logger.info('Environment variables validated successfully');
    return true;
  }

  getConfig() {
    this.validate();

    return {
      port: parseInt(process.env.PORT, 10),
      nodeEnv: process.env.NODE_ENV,
      db: {
        host: process.env.DB_HOST,
        port: parseInt(process.env.DB_PORT, 10),
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME,
        ssl: process.env.DB_CA_CERT ? { ca: process.env.DB_CA_CERT } : false,
      },
      logging: {
        level: process.env.LOG_LEVEL || 'info',
      },
      cache: {
        expiry: parseInt(process.env.CACHE_EXPIRY, 10) || 3600,
      },
      dataSources: {
        use247Sports: process.env.USE_247SPORTS === 'true',
        useOn3: process.env.USE_ON3 === 'true',
        useRivals: process.env.USE_RIVALS === 'true',
      },
      apiKeys: {
        on3: process.env.ON3_API_KEY,
        rivals: process.env.RIVALS_API_KEY,
        sports247: process.env._247SPORTS_API_KEY,
      },
    };
  }
}

const envValidator = new EnvironmentValidator();
export default envValidator;
