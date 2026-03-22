-- V003: Create analytical views
-- Idempotent: DROP and recreate (views have no data to lose)

-- use SupplierIntelligence
--go 

-- ai_output.VendorScoresLatest: scores from the latest completed run
IF EXISTS (
    SELECT 1 FROM sys.views v
    JOIN sys.schemas s ON v.schema_id = s.schema_id
    WHERE s.name = 'ai_output' AND v.name = 'VendorScoresLatest'
)
    DROP VIEW ai_output.VendorScoresLatest;
GO
CREATE VIEW ai_output.VendorScoresLatest AS
SELECT vs.*
FROM ai_output.VendorScores vs
INNER JOIN (
    SELECT MAX(vs2.RunId) AS MaxRunId
    FROM ai_output.VendorScores vs2
    INNER JOIN ml_admin.MlRunLog rl ON vs2.RunId = rl.Id
    WHERE rl.Status = 'COMPLETED'
) lr ON vs.RunId = lr.MaxRunId;
GO

-- ai_output.AnomalyFlagsLatest: anomalies from the latest completed run
IF EXISTS (
    SELECT 1 FROM sys.views v
    JOIN sys.schemas s ON v.schema_id = s.schema_id
    WHERE s.name = 'ai_output' AND v.name = 'AnomalyFlagsLatest'
)
    DROP VIEW ai_output.AnomalyFlagsLatest;
GO
CREATE VIEW ai_output.AnomalyFlagsLatest AS
SELECT af.*
FROM ai_output.AnomalyFlags af
INNER JOIN (
    SELECT MAX(af2.RunId) AS MaxRunId
    FROM ai_output.AnomalyFlags af2
    INNER JOIN ml_admin.MlRunLog rl ON af2.RunId = rl.Id
    WHERE rl.Status = 'COMPLETED'
) lr ON af.RunId = lr.MaxRunId;
GO

-- ai_output.ConsolidationLatestFlat: clusters + members, latest completed run
IF EXISTS (
    SELECT 1 FROM sys.views v
    JOIN sys.schemas s ON v.schema_id = s.schema_id
    WHERE s.name = 'ai_output' AND v.name = 'ConsolidationLatestFlat'
)
    DROP VIEW ai_output.ConsolidationLatestFlat;
GO
CREATE VIEW ai_output.ConsolidationLatestFlat AS
SELECT
    cc.Id                   AS ClusterId,
    cc.RunId,
    cc.ClusterLabel,
    cc.DominantCategory,
    cc.VendorCount,
    cc.TotalSpendAtStake,
    cc.EstimatedSavingPct,
    cc.EstimatedSavingAmount,
    cm.Id                   AS MemberId,
    cm.CanonicalVendorName,
    cm.VendorTotalSpend,
    cm.CategoriesSupplied
FROM ai_output.ConsolidationClusters cc
INNER JOIN (
    SELECT MAX(cc2.RunId) AS MaxRunId
    FROM ai_output.ConsolidationClusters cc2
    INNER JOIN ml_admin.MlRunLog rl ON cc2.RunId = rl.Id
    WHERE rl.Status = 'COMPLETED'
) lr ON cc.RunId = lr.MaxRunId
LEFT JOIN ai_output.ConsolidationMembers cm ON cm.ClusterId = cc.Id;
GO
