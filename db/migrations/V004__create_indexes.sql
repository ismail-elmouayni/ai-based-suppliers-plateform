-- V004: Create performance indexes
-- Idempotent: uses IF NOT EXISTS guards

-- use SupplierIntelligence
-- go 

-- procurement.ProcurementRecords
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ProcurementRecords_Vendor'
    AND object_id = OBJECT_ID('procurement.ProcurementRecords'))
    CREATE NONCLUSTERED INDEX IX_ProcurementRecords_Vendor
        ON procurement.ProcurementRecords (Vendor);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ProcurementRecords_Category'
    AND object_id = OBJECT_ID('procurement.ProcurementRecords'))
    CREATE NONCLUSTERED INDEX IX_ProcurementRecords_Category
        ON procurement.ProcurementRecords (Category);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ProcurementRecords_PO_Number'
    AND object_id = OBJECT_ID('procurement.ProcurementRecords'))
    CREATE NONCLUSTERED INDEX IX_ProcurementRecords_PO_Number
        ON procurement.ProcurementRecords (PO_Number);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ProcurementRecords_LoadedAt'
    AND object_id = OBJECT_ID('procurement.ProcurementRecords'))
    CREATE NONCLUSTERED INDEX IX_ProcurementRecords_LoadedAt
        ON procurement.ProcurementRecords (LoadedAt DESC);
GO

-- procurement.ResolvedVendors
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ResolvedVendors_RawVendorName'
    AND object_id = OBJECT_ID('procurement.ResolvedVendors'))
    CREATE NONCLUSTERED INDEX IX_ResolvedVendors_RawVendorName
        ON procurement.ResolvedVendors (RawVendorName);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ResolvedVendors_CanonicalVendorName'
    AND object_id = OBJECT_ID('procurement.ResolvedVendors'))
    CREATE NONCLUSTERED INDEX IX_ResolvedVendors_CanonicalVendorName
        ON procurement.ResolvedVendors (CanonicalVendorName);
GO

-- ai_output.VendorScores
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_VendorScores_RunId'
    AND object_id = OBJECT_ID('ai_output.VendorScores'))
    CREATE NONCLUSTERED INDEX IX_VendorScores_RunId
        ON ai_output.VendorScores (RunId);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_VendorScores_CanonicalVendorName'
    AND object_id = OBJECT_ID('ai_output.VendorScores'))
    CREATE NONCLUSTERED INDEX IX_VendorScores_CanonicalVendorName
        ON ai_output.VendorScores (CanonicalVendorName);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_VendorScores_PerformanceBand'
    AND object_id = OBJECT_ID('ai_output.VendorScores'))
    CREATE NONCLUSTERED INDEX IX_VendorScores_PerformanceBand
        ON ai_output.VendorScores (PerformanceBand);
GO

-- ai_output.AnomalyFlags
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_AnomalyFlags_RunId'
    AND object_id = OBJECT_ID('ai_output.AnomalyFlags'))
    CREATE NONCLUSTERED INDEX IX_AnomalyFlags_RunId
        ON ai_output.AnomalyFlags (RunId);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_AnomalyFlags_Severity'
    AND object_id = OBJECT_ID('ai_output.AnomalyFlags'))
    CREATE NONCLUSTERED INDEX IX_AnomalyFlags_Severity
        ON ai_output.AnomalyFlags (Severity);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_AnomalyFlags_CanonicalVendorName'
    AND object_id = OBJECT_ID('ai_output.AnomalyFlags'))
    CREATE NONCLUSTERED INDEX IX_AnomalyFlags_CanonicalVendorName
        ON ai_output.AnomalyFlags (CanonicalVendorName);
GO

-- ai_output.ConsolidationClusters
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ConsolidationClusters_RunId'
    AND object_id = OBJECT_ID('ai_output.ConsolidationClusters'))
    CREATE NONCLUSTERED INDEX IX_ConsolidationClusters_RunId
        ON ai_output.ConsolidationClusters (RunId);
GO

-- ml_admin.MlRunLog
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_MlRunLog_Status'
    AND object_id = OBJECT_ID('ml_admin.MlRunLog'))
    CREATE NONCLUSTERED INDEX IX_MlRunLog_Status
        ON ml_admin.MlRunLog (Status);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_MlRunLog_StartedAt'
    AND object_id = OBJECT_ID('ml_admin.MlRunLog'))
    CREATE NONCLUSTERED INDEX IX_MlRunLog_StartedAt
        ON ml_admin.MlRunLog (StartedAt DESC);
GO
