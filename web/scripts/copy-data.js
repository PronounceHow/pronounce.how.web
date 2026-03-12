#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Destination: ./data (inside web project)
const destDataDir = path.resolve(__dirname, '..', 'data');
const destWordsDir = path.join(destDataDir, 'words');

// Check if data already exists (e.g., uploaded to Vercel)
if (fs.existsSync(destWordsDir)) {
  console.log('✓ Data directory already exists at:', destDataDir);
  console.log('Skipping copy (data was likely uploaded directly)');
  process.exit(0);
}

// Source: ../../pronounce-how-data/data
const sourceDataDir = path.resolve(__dirname, '..', '..', '..', 'pronounce-how-data', 'data');

console.log('Copying data from:', sourceDataDir);
console.log('To:', destDataDir);

if (!fs.existsSync(sourceDataDir)) {
  console.error('ERROR: Source data directory not found:', sourceDataDir);
  console.error('This might be okay if data was already uploaded to the deployment platform');
  process.exit(0); // Exit gracefully instead of failing
}

// Copy the data directory
console.log('Copying data...');
fs.cpSync(sourceDataDir, destDataDir, { recursive: true });

console.log('✓ Data copied successfully');
