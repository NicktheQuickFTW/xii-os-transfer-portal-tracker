# XII-OS Transfer Portal Tracker

A comprehensive module for tracking and analyzing player transfers in real-time. Part of the XII-OS ecosystem.

## Features

- Real-time transfer monitoring
- Player statistics tracking
- Advanced analytics dashboard
- Multi-source data collection (On3, 247Sports, Rivals)
- RESTful API endpoints
- Automated data scraping agents

## Installation

### Prerequisites

- Node.js (v18 or higher)
- Python (v3.9 or higher)
- PostgreSQL (v15 or higher)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/xii-os-transfer-portal-tracker.git
cd xii-os-transfer-portal-tracker
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Usage

### Development

Start the development server:

```bash
npm run dev
```

The server will be available at `http://localhost:3001`.

### Production

Build and start the production server:

```bash
npm run build
npm start
```

## API Endpoints

### Player Data

- `GET /api/transfer-portal-tracker/players` - Get all players
- `GET /api/transfer-portal-tracker/players/search` - Search players by criteria
- `GET /api/transfer-portal-tracker/stats` - Get transfer portal statistics
- `GET /api/transfer-portal-tracker/trending` - Get trending transfers
- `GET /api/transfer-portal-tracker/compare` - Compare players
- `GET /api/transfer-portal-tracker/team-analysis` - Get team analysis
- `GET /api/transfer-portal-tracker/predictions` - Get transfer predictions

## Configuration

The module can be configured through environment variables:

- `PORT` - Server port (default: 3001)
- `DB_*` - Database configuration
- `CACHE_EXPIRY` - Cache duration in seconds
- `USE_247SPORTS` - Enable/disable 247Sports scraping
- `USE_ON3` - Enable/disable On3 scraping
- `USE_RIVALS` - Enable/disable Rivals scraping

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- XII-OS Team
- Data provided by On3, 247Sports, and Rivals 