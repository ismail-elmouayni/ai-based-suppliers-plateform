using SupplierIntelligence.Api.Models.DTOs;

namespace SupplierIntelligence.Api.Services;

public interface IAnomalyDetectionService
{
    Task<PagedResult<AnomalyFlagDto>> GetAnomaliesAsync(int page, int pageSize, string? severity, string? vendor, string? category);
    Task<PagedResult<AnomalyFlagDto>> GetBySeverityAsync(string severity, int page, int pageSize);
    Task<PagedResult<AnomalyFlagDto>> GetByVendorAsync(string vendorName, int page, int pageSize, string? severity);
    Task<PagedResult<AnomalyFlagDto>> GetByCategoryAsync(string category, int page, int pageSize, string? severity);
    Task<AnomalyFlagDto?> GetByIdAsync(long id);
}
