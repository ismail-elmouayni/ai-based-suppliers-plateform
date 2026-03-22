namespace SupplierIntelligence.Api.Models.Entities;

public class AnomalyFlag
{
    public long Id { get; set; }
    public long RunId { get; set; }
    public long? SourceRecordId { get; set; }
    public string? PO_Number { get; set; }
    public string? CanonicalVendorName { get; set; }
    public string? Category { get; set; }
    public decimal? Original_Spend { get; set; }
    public decimal? Spend { get; set; }
    public decimal? SpendGap { get; set; }
    public decimal? AnomalyScore { get; set; }
    public decimal? ZScore { get; set; }
    public string Severity { get; set; } = string.Empty;
    public string? ReasonString { get; set; }
    public DateTime CreatedAt { get; set; }
}
