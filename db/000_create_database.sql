-- Create Radar TRH database.
--
-- Run this connected to a maintenance database, for example:
--   psql postgres -f db/000_create_database.sql
--
-- Then initialize the schema:
--   psql radar_trh -f db/001_create_radar_raw.sql

CREATE DATABASE radar_trh;
