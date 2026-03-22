using SupplierIntelligence.Api.Models.Entities;

namespace SupplierIntelligence.Api.Services;

public interface IMlTriggerService
{
    Task<object> TriggerRunAsync(string runType);
    Task<object> GetStatusAsync();
    Task<object> GetRunsAsync(int page, int pageSize);
}
