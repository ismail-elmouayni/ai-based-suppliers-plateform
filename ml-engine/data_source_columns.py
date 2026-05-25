"""
DataSourceColumns — single source of truth for procurement DataFrame column names.

These names are shared across all pipeline modules regardless of the data source
(SQL Server in the main pipeline, Excel in standalone mode).
Centralising them here means a schema change only requires editing one file.
"""


class DataSourceColumns:
    # ------------------------------------------------------------------
    # Raw procurement record columns  (procurement.ProcurementRecords)
    # ------------------------------------------------------------------
    ID               = "Id"
    COUNTRY          = "Country"
    VENDOR           = "Vendor"            # raw vendor name (pre entity-resolution)
    CATEGORY         = "Category"
    PURCHASE_ORDERS_NUMBER        = "PO_Number"
    ITEM_DESCRIPTION = "Item_Description"
    ORIGINAL_SPEND   = "Original_Spend"
    OPEX_CAPEX       = "OPEX_CAPEX"
    SAVING           = "Saving"
    SAVING_PERCENT       = "Saving_Pct"
    SPEND            = "Spend"

    # ------------------------------------------------------------------
    # Post entity-resolution column (added to the DataFrame by the pipeline)
    # ------------------------------------------------------------------
    CANONICAL_VENDOR = "CanonicalVendorName"

    # ------------------------------------------------------------------
    # Optional enrichment columns (null-filled when absent in source data)
    # ------------------------------------------------------------------
    VAT_NUMBER       = "VATNumber"
