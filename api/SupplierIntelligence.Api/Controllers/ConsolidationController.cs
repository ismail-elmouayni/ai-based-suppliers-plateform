using Microsoft.AspNetCore.Mvc;
using SupplierIntelligence.Api.Models.DTOs;
using SupplierIntelligence.Api.Services;

namespace SupplierIntelligence.Api.Controllers;

[ApiController]
[Route("api/v1/consolidation")]
public class ConsolidationController : ControllerBase
{
    private readonly IConsolidationService _svc;

    public ConsolidationController(IConsolidationService svc) => _svc = svc;

    [HttpGet]
    public async Task<ActionResult<PagedResult<ConsolidationClusterDto>>> GetClusters(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] decimal? minSpend = null)
        => Ok(await _svc.GetClustersAsync(page, pageSize, minSpend));

    [HttpGet("{clusterId:long}")]
    public async Task<ActionResult<ConsolidationClusterDto>> GetCluster(long clusterId)
    {
        var cluster = await _svc.GetClusterByIdAsync(clusterId);
        if (cluster == null)
            throw new KeyNotFoundException($"Cluster {clusterId} not found.");
        return Ok(cluster);
    }

    [HttpGet("by-category/{category}")]
    public async Task<ActionResult<PagedResult<ConsolidationClusterDto>>> GetByCategory(
        string category,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
        => Ok(await _svc.GetByCategoryAsync(category, page, pageSize));

    [HttpGet("by-vendor/{vendorName}")]
    public async Task<ActionResult<PagedResult<ConsolidationClusterDto>>> GetByVendor(
        string vendorName,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
        => Ok(await _svc.GetByVendorAsync(vendorName, page, pageSize));
}
