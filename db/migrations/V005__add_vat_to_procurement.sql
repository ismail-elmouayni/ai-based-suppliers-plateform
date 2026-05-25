-- V005 — Add VATNumber to ProcurementRecords and ResolvedVendors
-- VATNumber is nullable: enrichment data only available for some vendors/sources.

ALTER TABLE procurement.ProcurementRecords
    ADD VATNumber NVARCHAR(50) NULL;

ALTER TABLE procurement.ResolvedVendors
    ADD VATNumber NVARCHAR(50) NULL;
