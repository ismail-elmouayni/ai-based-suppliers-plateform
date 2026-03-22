using SupplierIntelligence.Api.Models.DTOs;

namespace SupplierIntelligence.Api.Services;

public interface IConsolidationService
{
    Task<PagedResult<ConsolidationClusterDto>> GetClustersAsync(int page, int pageSize, decimal? minSpend);
    Task<ConsolidationClusterDto?> GetClusterByIdAsync(long clusterId);
    Task<PagedResult<ConsolidationClusterDto>> GetByCategoryAsync(string category, int page, int pageSize);
    Task<PagedResult<ConsolidationClusterDto>> GetByVendorAsync(string vendorName, int page, int pageSize);
}
