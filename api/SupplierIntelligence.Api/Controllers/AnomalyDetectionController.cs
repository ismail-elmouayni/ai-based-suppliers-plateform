using Microsoft.AspNetCore.Mvc;
using SupplierIntelligence.Api.Models.DTOs;
using SupplierIntelligence.Api.Services;

namespace SupplierIntelligence.Api.Controllers;

[ApiController]
[Route("api/v1/anomalies")]
public class AnomalyDetectionController : ControllerBase
{
    private readonly IAnomalyDetectionService _svc;

    public AnomalyDetectionController(IAnomalyDetectionService svc) => _svc = svc;

    [HttpGet]
    public async Task<ActionResult<PagedResult<AnomalyFlagDto>>> GetAnomalies(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? severity = null,
        [FromQuery] string? vendor = null,
        [FromQuery] string? category = null)
        => Ok(await _svc.GetAnomaliesAsync(page, pageSize, severity, vendor, category));

    [HttpGet("by-severity/{severity}")]
    public async Task<ActionResult<PagedResult<AnomalyFlagDto>>> GetBySeverity(
        string severity,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
        => Ok(await _svc.GetBySeverityAsync(severity, page, pageSize));

    [HttpGet("by-vendor/{vendorName}")]
    public async Task<ActionResult<PagedResult<AnomalyFlagDto>>> GetByVendor(
        string vendorName,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? severity = null)
        => Ok(await _svc.GetByVendorAsync(vendorName, page, pageSize, severity));

    [HttpGet("by-category/{category}")]
    public async Task<ActionResult<PagedResult<AnomalyFlagDto>>> GetByCategory(
        string category,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? severity = null)
        => Ok(await _svc.GetByCategoryAsync(category, page, pageSize, severity));

    [HttpGet("{id:long}")]
    public async Task<ActionResult<AnomalyFlagDto>> GetById(long id)
    {
        var flag = await _svc.GetByIdAsync(id);
        if (flag == null)
            throw new KeyNotFoundException($"Anomaly flag {id} not found.");
        return Ok(flag);
    }
}
