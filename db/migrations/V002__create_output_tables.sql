-- V002: Create AI output and admin tables
-- Idempotent: uses IF NOT EXISTS guards

-- use SupplierIntelligence
-- go 

-- ml_admin.MlRunLog
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'ml_admin' AND t.name = 'MlRunLog'
)
BEGIN
    CREATE TABLE ml_admin.MlRunLog (
        Id             BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunType        NVARCHAR(50)         NOT NULL,
        TriggeredBy    NVARCHAR(100)        NULL,
        Status         NVARCHAR(20)         NOT NULL DEFAULT 'PENDING',
        StartedAt      DATETIME2            NOT NULL DEFAULT SYSUTCDATETIME(),
        CompletedAt    DATETIME2            NULL,
        DurationMs     BIGINT               NULL,
        ErrorMessage   NVARCHAR(MAX)        NULL,
        ConfigSnapshot NVARCHAR(MAX)        NULL
    );
END;
GO

-- ai_output.VendorScores
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'ai_output' AND t.name = 'VendorScores'
)
BEGIN
    CREATE TABLE ai_output.VendorScores (
        Id                  BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunId               BIGINT              NOT NULL,
        CanonicalVendorName NVARCHAR(500)       NOT NULL,
        Category            NVARCHAR(200)       NULL,
        CompositeScore      DECIMAL(6,2)        NOT NULL,
        PerformanceBand     NVARCHAR(20)        NOT NULL,
        SavingPctNorm       DECIMAL(8,6)        NULL,
        SpendNorm           DECIMAL(8,6)        NULL,
        SpecializationNorm  DECIMAL(8,6)        NULL,
        RawSavingPct        DECIMAL(10,8)       NULL,
        RawTotalSpend       DECIMAL(18,4)       NULL,
        RawSpecialization   DECIMAL(8,6)        NULL,
        PurchaseCount       INT                 NOT NULL,
        CreatedAt           DATETIME2           NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

-- ai_output.ConsolidationClusters
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'ai_output' AND t.name = 'ConsolidationClusters'
)
BEGIN
    CREATE TABLE ai_output.ConsolidationClusters (
        Id                    BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunId                 BIGINT              NOT NULL,
        ClusterLabel          INT                 NOT NULL,
        DominantCategory      NVARCHAR(200)       NULL,
        VendorCount           INT                 NOT NULL,
        TotalSpendAtStake     DECIMAL(18,4)       NOT NULL,
        EstimatedSavingPct    DECIMAL(8,6)        NULL,
        EstimatedSavingAmount DECIMAL(18,4)       NULL,
        CreatedAt             DATETIME2           NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

-- ai_output.ConsolidationMembers
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'ai_output' AND t.name = 'ConsolidationMembers'
)
BEGIN
    CREATE TABLE ai_output.ConsolidationMembers (
        Id                  BIGINT IDENTITY(1,1) PRIMARY KEY,
        ClusterId           BIGINT              NOT NULL,
        CanonicalVendorName NVARCHAR(500)       NOT NULL,
        VendorTotalSpend    DECIMAL(18,4)       NULL,
        CategoriesSupplied  NVARCHAR(MAX)       NULL,
        CONSTRAINT FK_ConsolidationMembers_Clusters
            FOREIGN KEY (ClusterId) REFERENCES ai_output.ConsolidationClusters(Id)
    );
END;
GO

-- ai_output.AnomalyFlags
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'ai_output' AND t.name = 'AnomalyFlags'
)
BEGIN
    CREATE TABLE ai_output.AnomalyFlags (
        Id                  BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunId               BIGINT              NOT NULL,
        SourceRecordId      BIGINT              NULL,
        PO_Number           NVARCHAR(100)       NULL,
        CanonicalVendorName NVARCHAR(500)       NULL,
        Category            NVARCHAR(200)       NULL,
        Original_Spend      DECIMAL(18,4)       NULL,
        Spend               DECIMAL(18,4)       NULL,
        SpendGap            DECIMAL(18,4)       NULL,
        AnomalyScore        DECIMAL(8,6)        NULL,
        ZScore              DECIMAL(10,4)       NULL,
        Severity            NVARCHAR(10)        NOT NULL,
        ReasonString        NVARCHAR(MAX)       NULL,
        CreatedAt           DATETIME2           NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_AnomalyFlags_ProcurementRecords
            FOREIGN KEY (SourceRecordId) REFERENCES procurement.ProcurementRecords(Id)
    );
END;
GO
