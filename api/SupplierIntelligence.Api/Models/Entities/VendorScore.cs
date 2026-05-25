namespace SupplierIntelligence.Api.Models.Entities;

public class VendorScore
{
    public long Id { get; set; }
    public long RunId { get; set; }
    public string CanonicalVendorName { get; set; } = string.Empty;
    public string? Category { get; set; }
    public decimal CompositeScore { get; set; }
    public string PerformanceBand { get; set; } = string.Empty;
    public decimal? SavingPctNorm { get; set; }
    public decimal? SpendNorm { get; set; }
    public decimal? SpecializationNorm { get; set; }
    public decimal? RawSavingPct { get; set; }
    public decimal? RawTotalSpend { get; set; }
    public decimal? RawSpecialization { get; set; }
    public int PurchaseCount { get; set; }
    public DateTime CreatedAt { get; set; }
}
