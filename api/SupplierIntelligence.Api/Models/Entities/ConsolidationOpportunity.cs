namespace SupplierIntelligence.Api.Models.Entities;

public class ConsolidationOpportunity
{
    public long Id { get; set; }
    public long RunId { get; set; }
    public int ClusterLabel { get; set; }
    public string? DominantCategory { get; set; }
    public int VendorCount { get; set; }
    public decimal TotalSpendAtStake { get; set; }
    public decimal? EstimatedSavingPct { get; set; }
    public decimal? EstimatedSavingAmount { get; set; }
    public DateTime CreatedAt { get; set; }
    public List<ConsolidationMember> Members { get; set; } = new();
}

public class ConsolidationMember
{
    public long Id { get; set; }
    public long ClusterId { get; set; }
    public string CanonicalVendorName { get; set; } = string.Empty;
    public decimal? VendorTotalSpend { get; set; }
    public string? CategoriesSupplied { get; set; }
}
