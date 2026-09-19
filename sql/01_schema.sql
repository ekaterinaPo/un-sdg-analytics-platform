-- Project 08: UN SDG Analytics Platform
-- Database: SQLite (built-in Python sqlite3 — no installation required)
-- Load this via: conn = sqlite3.connect('data/processed/sdg_analytics.db')
--               conn.executescript(open('sql/01_schema.sql').read())

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- Reference tables
-- ============================================================

DROP TABLE IF EXISTS sdg_goals;
CREATE TABLE sdg_goals (
    goal_id     INTEGER PRIMARY KEY,
    goal_name   TEXT NOT NULL,
    goal_short  TEXT NOT NULL
);

INSERT INTO sdg_goals VALUES
(1,  'No Poverty',                                'No Poverty'),
(2,  'Zero Hunger',                               'Zero Hunger'),
(3,  'Good Health and Well-being',                'Good Health'),
(4,  'Quality Education',                         'Quality Education'),
(5,  'Gender Equality',                           'Gender Equality'),
(6,  'Clean Water and Sanitation',                'Clean Water'),
(7,  'Affordable and Clean Energy',               'Clean Energy'),
(8,  'Decent Work and Economic Growth',           'Decent Work'),
(9,  'Industry, Innovation and Infrastructure',   'Innovation'),
(10, 'Reduced Inequalities',                      'Reduced Inequalities'),
(11, 'Sustainable Cities and Communities',        'Sustainable Cities'),
(12, 'Responsible Consumption and Production',    'Responsible Consumption'),
(13, 'Climate Action',                            'Climate Action'),
(14, 'Life Below Water',                          'Life Below Water'),
(15, 'Life on Land',                              'Life on Land'),
(16, 'Peace, Justice and Strong Institutions',    'Peace & Justice'),
(17, 'Partnerships for the Goals',               'Partnerships');


DROP TABLE IF EXISTS countries;
CREATE TABLE countries (
    country_code    TEXT PRIMARY KEY,   -- ISO3, e.g. 'CAN'
    country_name    TEXT NOT NULL,
    region          TEXT,               -- UN regional groupings
    income_group    TEXT,               -- World Bank: Low/Lower-middle/Upper-middle/High
    population      INTEGER,
    gdp_per_capita  REAL
);


DROP TABLE IF EXISTS sdg_indicators;
CREATE TABLE sdg_indicators (
    indicator_code   TEXT PRIMARY KEY,  -- e.g. '1.1.1'
    goal_id          INTEGER REFERENCES sdg_goals(goal_id),
    target_code      TEXT,              -- e.g. '1.1'
    indicator_name   TEXT NOT NULL,
    unit             TEXT,
    target_value     REAL,              -- 2030 target where defined
    target_direction TEXT               -- 'higher_better' or 'lower_better'
);


-- ============================================================
-- Fact table: one row per country × indicator × year
-- ============================================================
DROP TABLE IF EXISTS sdg_values;
CREATE TABLE sdg_values (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code    TEXT REFERENCES countries(country_code),
    indicator_code  TEXT REFERENCES sdg_indicators(indicator_code),
    year            INTEGER NOT NULL,
    value           REAL,
    source          TEXT,
    series_code     TEXT
);

CREATE INDEX IF NOT EXISTS idx_sdg_country    ON sdg_values(country_code);
CREATE INDEX IF NOT EXISTS idx_sdg_indicator  ON sdg_values(indicator_code);
CREATE INDEX IF NOT EXISTS idx_sdg_year       ON sdg_values(year);


-- ============================================================
-- SDG Index scores (from Sustainable Development Report 2025)
-- ============================================================
DROP TABLE IF EXISTS sdg_index_scores;
CREATE TABLE sdg_index_scores (
    country_code    TEXT REFERENCES countries(country_code),
    year            INTEGER NOT NULL,
    sdg_index_score REAL,       -- 0–100, higher = better
    sdg_rank        INTEGER,
    PRIMARY KEY (country_code, year)
);
