-- V001: Create schemas and source tables
-- Idempotent: uses IF NOT EXISTS guards

-- use SupplierIntelligence
-- go 

-- Create schemas
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'procurement')
    EXEC('CREATE SCHEMA procurement');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'ai_output')
    EXEC('CREATE SCHEMA ai_output');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'ml_admin')
    EXEC('CREATE SCHEMA ml_admin');
GO

-- procurement.ProcurementRecords
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'procurement' AND t.name = 'ProcurementRecords'
)
BEGIN
    CREATE TABLE procurement.ProcurementRecords (
        Id               BIGINT IDENTITY(1,1) PRIMARY KEY,
        Country          NVARCHAR(100)        NULL,
        Vendor           NVARCHAR(500)        NOT NULL,
        Category         NVARCHAR(200)        NULL,
        PO_Number        NVARCHAR(100)        NULL,
        Item_Description NVARCHAR(1000)       NULL,
        Original_Spend   DECIMAL(18,4)        NULL,
        OPEX_CAPEX       NVARCHAR(10)         NULL,
        Saving           DECIMAL(18,4)        NULL,
        Saving_Pct       DECIMAL(10,8)        NULL,
        Spend            DECIMAL(18,4)        NULL,
        LoadedAt         DATETIME2            NOT NULL DEFAULT SYSUTCDATETIME(),
        SourceFile       NVARCHAR(500)        NULL
    );
END;
GO

-- procurement.ResolvedVendors
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = 'procurement' AND t.name = 'ResolvedVendors'
)
BEGIN
    CREATE TABLE procurement.ResolvedVendors (
        Id                  BIGINT IDENTITY(1,1) PRIMARY KEY,
        RawVendorName       NVARCHAR(500)    NOT NULL,
        CanonicalVendorName NVARCHAR(500)    NOT NULL,
        MatchScore          DECIMAL(5,2)     NULL,
        MatchMethod         NVARCHAR(50)     NULL,
        ResolutionRunId     BIGINT           NULL,
        CreatedAt           DATETIME2        NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO
