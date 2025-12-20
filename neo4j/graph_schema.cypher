// HIMARI Opus1 - Neo4j Knowledge Graph Schema
// Execute via: cypher-shell -u neo4j -p <password> < graph_schema.cypher

// ============================================================
// CONSTRAINTS AND INDEXES
// ============================================================
CREATE CONSTRAINT exchange_name IF NOT EXISTS
FOR (e:Exchange) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT asset_symbol IF NOT EXISTS
FOR (a:Asset) REQUIRE a.symbol IS UNIQUE;

CREATE CONSTRAINT pair_symbol IF NOT EXISTS
FOR (p:Pair) REQUIRE p.symbol IS UNIQUE;

CREATE CONSTRAINT wallet_address IF NOT EXISTS
FOR (w:Wallet) REQUIRE w.address IS UNIQUE;

CREATE INDEX cascade_timestamp IF NOT EXISTS
FOR (c:CascadeEvent) ON (c.timestamp);

CREATE INDEX transfer_timestamp IF NOT EXISTS
FOR (t:WhaleTransfer) ON (t.timestamp);

CREATE INDEX price_movement_timestamp IF NOT EXISTS
FOR (pm:PriceMovement) ON (pm.timestamp);

// ============================================================
// INITIAL ENTITIES - EXCHANGES
// ============================================================
MERGE (binance:Exchange {name: 'binance'})
SET binance.id = 'EX_BINANCE', binance.created_at = datetime();

MERGE (kraken:Exchange {name: 'kraken'})
SET kraken.id = 'EX_KRAKEN', kraken.created_at = datetime();

MERGE (bybit:Exchange {name: 'bybit'})
SET bybit.id = 'EX_BYBIT', bybit.created_at = datetime();

MERGE (deribit:Exchange {name: 'deribit'})
SET deribit.id = 'EX_DERIBIT', deribit.created_at = datetime();

MERGE (coinbase:Exchange {name: 'coinbase'})
SET coinbase.id = 'EX_COINBASE', coinbase.created_at = datetime();

// ============================================================
// INITIAL ENTITIES - ASSETS
// ============================================================
MERGE (btc:Asset {symbol: 'BTC'})
SET btc.id = 'ASSET_BTC', btc.name = 'Bitcoin';

MERGE (eth:Asset {symbol: 'ETH'})
SET eth.id = 'ASSET_ETH', eth.name = 'Ethereum';

MERGE (usdt:Asset {symbol: 'USDT'})
SET usdt.id = 'ASSET_USDT', usdt.name = 'Tether';

MERGE (usdc:Asset {symbol: 'USDC'})
SET usdc.id = 'ASSET_USDC', usdc.name = 'USD Coin';

MERGE (sol:Asset {symbol: 'SOL'})
SET sol.id = 'ASSET_SOL', sol.name = 'Solana';

// ============================================================
// INITIAL ENTITIES - TRADING PAIRS
// ============================================================
MERGE (btc_usdt:Pair {symbol: 'BTC/USDT'})
SET btc_usdt.id = 'PAIR_BTCUSDT';

MERGE (eth_usdt:Pair {symbol: 'ETH/USDT'})
SET eth_usdt.id = 'PAIR_ETHUSDT';

MERGE (sol_usdt:Pair {symbol: 'SOL/USDT'})
SET sol_usdt.id = 'PAIR_SOLUSDT';

// ============================================================
// RELATIONSHIPS - PAIR TO ASSETS
// ============================================================
MATCH (btc_usdt:Pair {symbol: 'BTC/USDT'})
MATCH (btc:Asset {symbol: 'BTC'})
MATCH (usdt:Asset {symbol: 'USDT'})
MERGE (btc_usdt)-[:BASE_ASSET]->(btc)
MERGE (btc_usdt)-[:QUOTE_ASSET]->(usdt);

MATCH (eth_usdt:Pair {symbol: 'ETH/USDT'})
MATCH (eth:Asset {symbol: 'ETH'})
MATCH (usdt:Asset {symbol: 'USDT'})
MERGE (eth_usdt)-[:BASE_ASSET]->(eth)
MERGE (eth_usdt)-[:QUOTE_ASSET]->(usdt);

MATCH (sol_usdt:Pair {symbol: 'SOL/USDT'})
MATCH (sol:Asset {symbol: 'SOL'})
MATCH (usdt:Asset {symbol: 'USDT'})
MERGE (sol_usdt)-[:BASE_ASSET]->(sol)
MERGE (sol_usdt)-[:QUOTE_ASSET]->(usdt);

// ============================================================
// RELATIONSHIPS - EXCHANGE LISTINGS
// ============================================================
MATCH (binance:Exchange {name: 'binance'})
MATCH (btc_usdt:Pair {symbol: 'BTC/USDT'})
MATCH (eth_usdt:Pair {symbol: 'ETH/USDT'})
MATCH (sol_usdt:Pair {symbol: 'SOL/USDT'})
MERGE (binance)-[:LISTS]->(btc_usdt)
MERGE (binance)-[:LISTS]->(eth_usdt)
MERGE (binance)-[:LISTS]->(sol_usdt);

MATCH (kraken:Exchange {name: 'kraken'})
MATCH (btc_usdt:Pair {symbol: 'BTC/USDT'})
MATCH (eth_usdt:Pair {symbol: 'ETH/USDT'})
MERGE (kraken)-[:LISTS]->(btc_usdt)
MERGE (kraken)-[:LISTS]->(eth_usdt);

// ============================================================
// VERIFY SETUP
// ============================================================
MATCH (e:Exchange) RETURN e.name AS exchange, e.id AS id;
MATCH (a:Asset) RETURN a.symbol AS asset, a.name AS name;
MATCH (p:Pair) RETURN p.symbol AS pair;
