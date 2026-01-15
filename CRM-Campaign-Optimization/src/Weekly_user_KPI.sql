WITH CONSENTED_PLAYERS AS (
    SELECT DISTINCT p.GPID
    FROM DW_WAREHOUSE.PUBLIC.GGCORE_DISTINCT_PLAYER AS P
    
    -- Join marketing consent
    JOIN DW_WAREHOUSE.PUBLIC.GGCORE_PLAYER_MARKETING_AGREEMENT AS C 
        ON p.id = c.player_id
        
    WHERE 
        c.CHANNEL_TYPE = 'Email'
        AND c.PRODUCT_TYPE = 'Casino'
        AND c.IS_MARKETING_CONSENT = TRUE
    
        -- Exclude active game limits
        AND NOT EXISTS (
            SELECT 1
            FROM DW_WAREHOUSE.PUBLIC.GGCORE_PLAYER_RESPONSIBLE_GAMING_GAME_LIMIT AS L
            WHERE L.GP_ID = P.GPID
            AND (L.CASINO = TRUE OR L.SLOT = TRUE OR L.LIVEDEALER = TRUE)
        )
        -- Exclude self-excluded / promotion disabled
        AND NOT EXISTS (
            SELECT 1
            FROM DW_WAREHOUSE.PUBLIC.GP_ACCOUNT AS A
            WHERE A.GP_ID = P.GPID
            AND (A.IS_SELF_EXCLUDED = TRUE OR A.IS_PROMOTION_ENABLED = FALSE)
        )
        -- Exclude non-active status
        AND NOT EXISTS (
            SELECT 1
            FROM DW_WAREHOUSE.PUBLIC.GP_ACCOUNT_STATUS AS S
            WHERE S.GP_ID = P.GPID
            AND S.STATUS != 'ACTIVE'
        )
        -- Wallet must be active
        AND EXISTS (
            SELECT 1
            FROM DW_WAREHOUSE.PUBLIC.GGCORE_WALLET AS W
            WHERE W.ACCOUNT_ID = P.ACCOUNTID 
            AND W.IS_ACTIVE = TRUE
        )
),

GAME_RTP AS (
    SELECT GAME_CODE, GAME_RTP
    FROM (
        SELECT 
            GAME_CODE, 
            GAME_RTP,
            ROW_NUMBER() OVER (PARTITION BY GAME_CODE ORDER BY UPDATED_AT DESC) AS rn
        FROM DW_WAREHOUSE.PUBLIC.CP_STATS_PERIODIC_DAILY
    )
    WHERE rn = 1
),

-- Top Category is now calculated on the FULL window (2024-01-01 to Present)
top_category AS (
    SELECT *
    FROM (
        SELECT 
            GP_ID,
            CATEGORY_ID,
            SUM(BET) AS total_bet,
            ROW_NUMBER() OVER (PARTITION BY GP_ID ORDER BY SUM(BET) DESC) AS rn
        FROM DW_WAREHOUSE.PUBLIC.GP_STATISTICS_GAME_CASINO
        WHERE AGGREGATED_AT >= '2024-01-01' -- Changed from BETWEEN to >=
        AND SITE_ID IN ('GGPUKE', 'EVPUKE', 'Natural8', 'GGPOK', 'GGPJP', 'GGPUA', 'GGPCOM', 'GGPUK', 'GGPEU', 'GGPFI', 'GGPHU', 'GGPPL')
        GROUP BY GP_ID, CATEGORY_ID
    ) ranked
    WHERE rn = 1
),

-- Single GPID check on the FULL window
SINGLE_GPID_USERS AS (
    SELECT 
        NICKNAME
    FROM DW_WAREHOUSE.PUBLIC.GP_STATISTICS_GAME_CASINO
    WHERE AGGREGATED_AT >= '2024-01-01' 
    GROUP BY 
        NICKNAME
    HAVING 
        COUNT(DISTINCT GP_ID) = 1 
),

LATEST_INFO AS (
  SELECT
    GGPASS_ID,
    GP_ID,
    NICKNAME,
    BRAND_ID,
    SITE_ID
  FROM (
    SELECT
      GGPASS_ID,
      GP_ID,
      NICKNAME,
      BRAND_ID,
      SITE_ID,
      AGGREGATED_AT,
      ROW_NUMBER() OVER (PARTITION BY GP_ID ORDER BY AGGREGATED_AT DESC) AS rn
    FROM DW_WAREHOUSE.PUBLIC.GP_STATISTICS_GAME_CASINO
    WHERE AGGREGATED_AT >= '2024-01-01'
  ) latest
  WHERE rn = 1
)

SELECT 
    DATE_TRUNC('WEEK', GC.AGGREGATED_AT) AS GAME_WEEK,
    GC.GGPASS_ID,
    REPLACE(GC.GGPASS_ID, '-', '') AS CID,
    LN.NICKNAME, 
    LN.BRAND_ID,
    LN.SITE_ID,
    TC.CATEGORY_ID AS TOP_CATEGORY,
    
    SUM(GC.BET) AS BET,
    SUM(GC.GGR) AS GGR,
    SUM(GC.BET * (1 - COALESCE(R.GAME_RTP, 0.96))) AS THEO_WIN, 
    COUNT(DISTINCT GC.AGGREGATED_AT) AS DAYS_PLAYED
    
FROM 
    DW_WAREHOUSE.PUBLIC.GP_STATISTICS_GAME_CASINO AS GC

-- Joins
JOIN CONSENTED_PLAYERS AS C ON C.GPID = GC.GP_ID
JOIN SINGLE_GPID_USERS AS SGU ON SGU.NICKNAME = GC.NICKNAME
LEFT JOIN GAME_RTP AS R ON R.GAME_CODE = GC.GAME_TYPE
LEFT JOIN TOP_CATEGORY AS TC ON TC.GP_ID = GC.GP_ID
LEFT JOIN LATEST_INFO AS LN ON LN.GP_ID = GC.GP_ID
    
WHERE 
    -- 1. METRICS TIMEFRAME:
    -- We want all data from DEC 1st 2025 onwards 
    GC.AGGREGATED_AT >= '2025-12-01' 
    
    AND gc.site_id IN ('GGPUKE', 'EVPUKE', 'Natural8', 'GGPOK', 'GGPJP', 'GGPUA', 'GGPCOM', 'GGPUK', 'GGPEU', 'GGPFI', 'GGPHU', 'GGPPL')
    AND GC.GENERAL_GAME_TYPE = 'JDBGAMING'

    
GROUP BY 
    DATE_TRUNC('WEEK', GC.AGGREGATED_AT),
    GC.GGPASS_ID,
    LN.NICKNAME,
    LN.SITE_ID,
    LN.BRAND_ID,
    TC.CATEGORY_ID

HAVING 
    SUM(GC.BET) > 0 AND COUNT(DISTINCT GC.AGGREGATED_AT) > 0;

