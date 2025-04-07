import supabase from '../config/supabase.js';
import logger from '../config/logger.js';

export const roles = {
  ADMIN: 'admin',
  SCOUT: 'scout',
  USER: 'user',
};

// Middleware to check if user is authenticated
export const requireAuth = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      return res.status(401).json({ error: 'No authorization header' });
    }

    const token = authHeader.replace('Bearer ', '');
    const {
      data: { user },
      error,
    } = await supabase.auth.getUser(token);

    if (error || !user) {
      return res.status(401).json({ error: 'Invalid or expired token' });
    }

    // Add user and their role to the request object
    req.user = user;
    req.userRole = user.user_metadata.role || roles.USER;

    next();
  } catch (error) {
    logger.error('Authentication error:', error);
    res.status(500).json({ error: 'Authentication failed' });
  }
};

// Middleware to check user role
export const requireRole = allowedRoles => {
  return (req, res, next) => {
    if (!req.user || !req.userRole) {
      return res.status(401).json({ error: 'Authentication required' });
    }

    if (!allowedRoles.includes(req.userRole)) {
      return res.status(403).json({ error: 'Insufficient permissions' });
    }

    next();
  };
};
