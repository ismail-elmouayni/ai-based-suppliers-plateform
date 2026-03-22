using Microsoft.AspNetCore.Mvc;
using SupplierIntelligence.Api.Models.DTOs;
using SupplierIntelligence.Api.Services;

namespace SupplierIntelligence.Api.Controllers;

[ApiController]
[Route("api/v1/vendor-scores")]
public class VendorRankingController : ControllerBase
{
    private readonly IVendorRankingService _svc;

    public VendorRankingController(IVendorRankingService svc) => _svc = svc;

    [HttpGet]
    public async Task<ActionResult<PagedResult<VendorScoreDto>>> GetScores(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? band = null,
        [FromQuery] decimal? minScore = null,
        [FromQuery] decimal? maxScore = null)
        => Ok(await _svc.GetScoresAsync(page, pageSize, band, minScore, maxScore));

    [HttpGet("by-category/{category}")]
    public async Task<ActionResult<PagedResult<VendorScoreDto>>> GetByCategory(
        string category,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? band = null)
        => Ok(await _svc.GetByCategoryAsync(category, page, pageSize, band));

    [HttpGet("by-vendor/{vendorName}")]
    public async Task<ActionResult<PagedResult<VendorScoreDto>>> GetByVendor(
        string vendorName,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
        => Ok(await _svc.GetByVendorAsync(vendorName, page, pageSize));

    [HttpGet("by-band/{band}")]
    public async Task<ActionResult<PagedResult<VendorScoreDto>>> GetByBand(
        string band,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? category = null)
        => Ok(await _svc.GetByBandAsync(band, page, pageSize, category));
}
