using Microsoft.EntityFrameworkCore;
using SupplierIntelligence.Api.Data;
using SupplierIntelligence.Api.Models.DTOs;
using SupplierIntelligence.Api.Models.Entities;

namespace SupplierIntelligence.Api.Services;

public class AnomalyDetectionService : IAnomalyDetectionService
{
    private readonly AppDbContext _db;

    public AnomalyDetectionService(AppDbContext db) => _db = db;

    private static AnomalyFlagDto ToDto(AnomalyFlag e) => new()
    {
        Id = e.Id,
        PO_Number = e.PO_Number,
        CanonicalVendorName = e.CanonicalVendorName,
        Category = e.Category,
        Original_Spend = e.Original_Spend,
        Spend = e.Spend,
        SpendGap = e.SpendGap,
        AnomalyScore = e.AnomalyScore,
        ZScore = e.ZScore,
        Severity = e.Severity,
        ReasonString = e.ReasonString,
    };

    public async Task<PagedResult<AnomalyFlagDto>> GetAnomaliesAsync(
        int page, int pageSize, string? severity, string? vendor, string? category)
    {
        var query = _db.AnomalyFlags.AsQueryable();
        if (!string.IsNullOrEmpty(severity))
            query = query.Where(x => x.Severity == severity.ToUpper());
        if (!string.IsNullOrEmpty(vendor))
            query = query.Where(x => x.CanonicalVendorName != null
                && EF.Functions.Like(x.CanonicalVendorName, $"%{vendor}%"));
        if (!string.IsNullOrEmpty(category))
            query = query.Where(x => x.Category != null
                && EF.Functions.Like(x.Category, $"%{category}%"));

        return await PaginateAsync(query.OrderByDescending(x => x.AnomalyScore), page, pageSize);
    }

    public async Task<PagedResult<AnomalyFlagDto>> GetBySeverityAsync(
        string severity, int page, int pageSize)
    {
        var query = _db.AnomalyFlags
            .Where(x => x.Severity == severity.ToUpper())
            .OrderByDescending(x => x.AnomalyScore);
        return await PaginateAsync(query, page, pageSize);
    }

    public async Task<PagedResult<AnomalyFlagDto>> GetByVendorAsync(
        string vendorName, int page, int pageSize, string? severity)
    {
        var query = _db.AnomalyFlags
            .Where(x => x.CanonicalVendorName != null
                && EF.Functions.Like(x.CanonicalVendorName, $"%{vendorName}%"))
            .AsQueryable();
        if (!string.IsNullOrEmpty(severity))
            query = query.Where(x => x.Severity == severity.ToUpper());
        return await PaginateAsync(query.OrderByDescending(x => x.AnomalyScore), page, pageSize);
    }

    public async Task<PagedResult<AnomalyFlagDto>> GetByCategoryAsync(
        string category, int page, int pageSize, string? severity)
    {
        var query = _db.AnomalyFlags
            .Where(x => x.Category != null
                && EF.Functions.Like(x.Category, $"%{category}%"))
            .AsQueryable();
        if (!string.IsNullOrEmpty(severity))
            query = query.Where(x => x.Severity == severity.ToUpper());
        return await PaginateAsync(query.OrderByDescending(x => x.AnomalyScore), page, pageSize);
    }

    public async Task<AnomalyFlagDto?> GetByIdAsync(long id)
    {
        // AnomalyFlag is a keyless view; filter by Id column directly
        var entity = await _db.AnomalyFlags
            .Where(x => x.Id == id)
            .FirstOrDefaultAsync();
        return entity == null ? null : ToDto(entity);
    }

    private static async Task<PagedResult<AnomalyFlagDto>> PaginateAsync(
        IOrderedQueryable<AnomalyFlag> query, int page, int pageSize)
    {
        var total = await query.CountAsync();
        // Materialize first; ToDto() cannot be translated to SQL
        var entities = await query.Skip((page - 1) * pageSize).Take(pageSize).ToListAsync();
        var items = entities.Select(ToDto).ToList();
        return PagedResult<AnomalyFlagDto>.Create(items, total, page, pageSize);
    }
}
