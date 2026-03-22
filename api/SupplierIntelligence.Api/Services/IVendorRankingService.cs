using SupplierIntelligence.Api.Models.DTOs;

namespace SupplierIntelligence.Api.Services;

public interface IVendorRankingService
{
    Task<PagedResult<VendorScoreDto>> GetScoresAsync(int page, int pageSize, string? band, decimal? minScore, decimal? maxScore);
    Task<PagedResult<VendorScoreDto>> GetByCategoryAsync(string category, int page, int pageSize, string? band);
    Task<PagedResult<VendorScoreDto>> GetByVendorAsync(string vendorName, int page, int pageSize);
    Task<PagedResult<VendorScoreDto>> GetByBandAsync(string band, int page, int pageSize, string? category);
}
