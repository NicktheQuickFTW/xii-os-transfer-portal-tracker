import React, { useState, useEffect } from 'react';
import { Box, Typography } from '@mui/material';

const TransferPortalTracker = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = async () => {
    try {
      console.log(
        '⚡ Fetching stats from API endpoint: /api/transfer-portal-tracker/stats'
      );
      const response = await fetch('/api/transfer-portal-tracker/stats');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setStats(data);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching stats:', err);
      setError(
        `Failed to fetch transfer portal tracker statistics: ${err.message}`
      );
      setLoading(false);
    }
  };

  useEffect(() => {
    console.log(
      'TransferPortalTracker component mounted - calling fetchStats()'
    );
    fetchStats();
  }, []);

  return (
    <Box className="transfer-portal-tracker" sx={{ p: 3 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Transfer Portal Tracker
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Track and analyze player transfers in real-time
        </Typography>
      </Box>
    </Box>
  );
};

export default TransferPortalTracker;
