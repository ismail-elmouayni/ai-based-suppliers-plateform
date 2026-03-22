using Microsoft.EntityFrameworkCore;
using SupplierIntelligence.Api.Data;
using SupplierIntelligence.Api.Models.DTOs;

namespace SupplierIntelligence.Api.Services;

public class MlTriggerService : IMlTriggerService
{
    private readonly HttpClient _http;
    private readonly AppDbContext _db;
    private readonly ILogger<MlTriggerService> _logger;

    public MlTriggerService(
        IHttpClientFactory httpClientFactory,
        AppDbContext db,
        ILogger<MlTriggerService> logger)
    {
        _http = httpClientFactory.CreateClient("MlEngine");
        _db = db;
        _logger = logger;
    }

    public async Task<object> TriggerRunAsync(string runType)
    {
        try
        {
            var payload = new { runType };
            var response = await _http.PostAsJsonAsync("/run", payload);
            var body = await response.Content.ReadFromJsonAsync<object>();
            return body ?? new { status = (int)response.StatusCode };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to trigger ML run");
            throw;
        }
    }

    public async Task<object> GetStatusAsync()
    {
        var latest = await _db.MlRunLogs
            .OrderByDescending(r => r.StartedAt)
            .FirstOrDefaultAsync();

        if (latest == null)
            return new { status = "NO_RUNS" };

        return new
        {
            latest.Id,
            latest.RunType,
            latest.Status,
            StartedAt = latest.StartedAt.ToString("O"),
            CompletedAt = latest.CompletedAt?.ToString("O"),
            latest.DurationMs,
            latest.ErrorMessage,
        };
    }

    public async Task<object> GetRunsAsync(int page, int pageSize)
    {
        var query = _db.MlRunLogs.OrderByDescending(r => r.StartedAt);
        var total = await query.CountAsync();
        var items = await query
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(r => new
            {
                r.Id,
                r.RunType,
                r.Status,
                StartedAt = r.StartedAt.ToString("O"),
                CompletedAt = r.CompletedAt != null ? r.CompletedAt.Value.ToString("O") : null,
                r.DurationMs,
                r.ErrorMessage,
            })
            .ToListAsync();

        return PagedResult<object>.Create(
            items.Cast<object>().ToList(), total, page, pageSize);
    }
}
