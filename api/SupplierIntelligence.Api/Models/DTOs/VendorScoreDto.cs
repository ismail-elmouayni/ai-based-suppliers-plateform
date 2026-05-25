namespace SupplierIntelligence.Api.Models.DTOs;

public class VendorScoreDto
{
    public long Id { get; set; }
    public string CanonicalVendorName { get; set; } = string.Empty;
    public string? Category { get; set; }
    public decimal CompositeScore { get; set; }
    public string PerformanceBand { get; set; } = string.Empty;
    public decimal? SavingPctDisplayPct => RawSavingPct.HasValue ? (decimal?)(RawSavingPct.Value * 100) : null;
    public decimal? RawSavingPct { get; set; }
    public decimal? RawTotalSpend { get; set; }
    public decimal? RawSpecialization { get; set; }
    public int PurchaseCount { get; set; }
}
