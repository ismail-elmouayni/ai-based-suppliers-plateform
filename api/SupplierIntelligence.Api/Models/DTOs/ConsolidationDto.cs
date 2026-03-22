namespace SupplierIntelligence.Api.Models.DTOs;

public class ConsolidationClusterDto
{
    public long Id { get; set; }
    public int ClusterLabel { get; set; }
    public string? DominantCategory { get; set; }
    public int VendorCount { get; set; }
    public decimal TotalSpendAtStake { get; set; }
    public decimal? EstimatedSavingPct { get; set; }
    public decimal? EstimatedSavingAmount { get; set; }
    public List<ConsolidationMemberDto> Members { get; set; } = new();
}

public class ConsolidationMemberDto
{
    public long Id { get; set; }
    public string CanonicalVendorName { get; set; } = string.Empty;
    public decimal? VendorTotalSpend { get; set; }
    public string? CategoriesSupplied { get; set; }
}
