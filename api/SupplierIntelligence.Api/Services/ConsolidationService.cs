using Microsoft.EntityFrameworkCore;
using SupplierIntelligence.Api.Data;
using SupplierIntelligence.Api.Models.DTOs;
using SupplierIntelligence.Api.Models.Entities;

namespace SupplierIntelligence.Api.Services;

public class ConsolidationService : IConsolidationService
{
    private readonly AppDbContext _db;

    public ConsolidationService(AppDbContext db) => _db = db;

    /// <summary>Returns the latest completed run ID, or null if none.</summary>
    private long? GetLatestRunId()
        => _db.MlRunLogs
            .Where(r => r.Status == "COMPLETED")
            .OrderByDescending(r => r.Id)
            .Select(r => (long?)r.Id)
            .FirstOrDefault();

    private IQueryable<ConsolidationOpportunity>? LatestClusters()
    {
        var runId = GetLatestRunId();
        if (runId == null) return null;
        return _db.ConsolidationClusters
            .Include(c => c.Members)
            .Where(c => c.RunId == runId.Value);
    }

    private static PagedResult<ConsolidationClusterDto> EmptyPage(int page, int pageSize)
        => PagedResult<ConsolidationClusterDto>.Create([], 0, page, pageSize);

    private static ConsolidationClusterDto ToDto(ConsolidationOpportunity e) => new()
    {
        Id = e.Id,
        ClusterLabel = e.ClusterLabel,
        DominantCategory = e.DominantCategory,
        VendorCount = e.VendorCount,
        TotalSpendAtStake = e.TotalSpendAtStake,
        EstimatedSavingPct = e.EstimatedSavingPct,
        EstimatedSavingAmount = e.EstimatedSavingAmount,
        Members = e.Members.Select(m => new ConsolidationMemberDto
        {
            Id = m.Id,
            CanonicalVendorName = m.CanonicalVendorName,
            VendorTotalSpend = m.VendorTotalSpend,
            CategoriesSupplied = m.CategoriesSupplied,
        }).ToList(),
    };

    public async Task<PagedResult<ConsolidationClusterDto>> GetClustersAsync(
        int page, int pageSize, decimal? minSpend)
    {
        var query = LatestClusters();
        if (query == null) return EmptyPage(page, pageSize);

        if (minSpend.HasValue)
            query = query.Where(c => c.TotalSpendAtStake >= minSpend.Value);

        var total = await query.CountAsync();
        var entities = await query
            .OrderByDescending(c => c.TotalSpendAtStake)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();
        var items = entities.Select(ToDto).ToList();
        return PagedResult<ConsolidationClusterDto>.Create(items, total, page, pageSize);
    }

    public async Task<ConsolidationClusterDto?> GetClusterByIdAsync(long clusterId)
    {
        var cluster = await _db.ConsolidationClusters
            .Include(c => c.Members)
            .FirstOrDefaultAsync(c => c.Id == clusterId);
        return cluster == null ? null : ToDto(cluster);
    }

    public async Task<PagedResult<ConsolidationClusterDto>> GetByCategoryAsync(
        string category, int page, int pageSize)
    {
        var base_ = LatestClusters();
        if (base_ == null) return EmptyPage(page, pageSize);
        var query = base_
            .Where(c => c.DominantCategory != null
                        && EF.Functions.Like(c.DominantCategory, $"%{category}%"));

        var total = await query.CountAsync();
        var entities = await query
            .OrderByDescending(c => c.TotalSpendAtStake)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();
        var items = entities.Select(ToDto).ToList();
        return PagedResult<ConsolidationClusterDto>.Create(items, total, page, pageSize);
    }

    public async Task<PagedResult<ConsolidationClusterDto>> GetByVendorAsync(
        string vendorName, int page, int pageSize)
    {
        var base_ = LatestClusters();
        if (base_ == null) return EmptyPage(page, pageSize);
        var query = base_
            .Where(c => c.Members.Any(m =>
                EF.Functions.Like(m.CanonicalVendorName, $"%{vendorName}%")));

        var total = await query.CountAsync();
        var entities = await query
            .OrderByDescending(c => c.TotalSpendAtStake)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();
        var items = entities.Select(ToDto).ToList();
        return PagedResult<ConsolidationClusterDto>.Create(items, total, page, pageSize);
    }
}
