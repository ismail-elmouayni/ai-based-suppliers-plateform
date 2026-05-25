using Microsoft.EntityFrameworkCore;
using SupplierIntelligence.Api.Data;
using SupplierIntelligence.Api.Models.DTOs;
using SupplierIntelligence.Api.Models.Entities;

namespace SupplierIntelligence.Api.Services;

public class VendorRankingService : IVendorRankingService
{
    private readonly AppDbContext _db;

    public VendorRankingService(AppDbContext db) => _db = db;

    private static VendorScoreDto ToDto(VendorScore e) => new()
    {
        Id = e.Id,
        CanonicalVendorName = e.CanonicalVendorName,
        Category = e.Category,
        CompositeScore = e.CompositeScore,
        PerformanceBand = e.PerformanceBand,
        RawSavingPct = e.RawSavingPct,
        RawTotalSpend = e.RawTotalSpend,
        RawSpecialization = e.RawSpecialization,
        PurchaseCount = e.PurchaseCount,
    };

    public async Task<PagedResult<VendorScoreDto>> GetScoresAsync(
        int page, int pageSize, string? band, decimal? minScore, decimal? maxScore)
    {
        var query = _db.VendorScores.AsQueryable();
        if (!string.IsNullOrEmpty(band))
            query = query.Where(x => x.PerformanceBand == band.ToUpper());
        if (minScore.HasValue)
            query = query.Where(x => x.CompositeScore >= minScore.Value);
        if (maxScore.HasValue)
            query = query.Where(x => x.CompositeScore <= maxScore.Value);

        return await PaginateAsync(query.OrderByDescending(x => x.CompositeScore), page, pageSize);
    }

    public async Task<PagedResult<VendorScoreDto>> GetByCategoryAsync(
        string category, int page, int pageSize, string? band)
    {
        var query = _db.VendorScores
            .Where(x => x.Category != null && EF.Functions.Like(x.Category, category))
            .AsQueryable();
        if (!string.IsNullOrEmpty(band))
            query = query.Where(x => x.PerformanceBand == band.ToUpper());
        return await PaginateAsync(query.OrderByDescending(x => x.CompositeScore), page, pageSize);
    }

    public async Task<PagedResult<VendorScoreDto>> GetByVendorAsync(
        string vendorName, int page, int pageSize)
    {
        var query = _db.VendorScores
            .Where(x => EF.Functions.Like(x.CanonicalVendorName, $"%{vendorName}%"))
            .OrderByDescending(x => x.CompositeScore);
        return await PaginateAsync(query, page, pageSize);
    }

    public async Task<PagedResult<VendorScoreDto>> GetByBandAsync(
        string band, int page, int pageSize, string? category)
    {
        var query = _db.VendorScores
            .Where(x => x.PerformanceBand == band.ToUpper())
            .AsQueryable();
        if (!string.IsNullOrEmpty(category))
            query = query.Where(x => x.Category != null && EF.Functions.Like(x.Category, category));
        return await PaginateAsync(query.OrderByDescending(x => x.CompositeScore), page, pageSize);
    }

    private static async Task<PagedResult<VendorScoreDto>> PaginateAsync(
        IOrderedQueryable<VendorScore> query, int page, int pageSize)
    {
        var total = await query.CountAsync();
        // Materialize to List<VendorScore> first; ToDto() cannot be translated to SQL
        var entities = await query.Skip((page - 1) * pageSize).Take(pageSize).ToListAsync();
        var items = entities.Select(ToDto).ToList();
        return PagedResult<VendorScoreDto>.Create(items, total, page, pageSize);
    }
}
