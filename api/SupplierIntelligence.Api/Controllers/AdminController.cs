using Microsoft.AspNetCore.Mvc;
using SupplierIntelligence.Api.Infrastructure;
using SupplierIntelligence.Api.Services;

namespace SupplierIntelligence.Api.Controllers;

[ApiController]
[Route("api/v1/admin")]
public class AdminController : ControllerBase
{
    private readonly IMlTriggerService _mlSvc;
    private readonly ConfigSummaryReader _configReader;

    public AdminController(IMlTriggerService mlSvc, ConfigSummaryReader configReader)
    {
        _mlSvc = mlSvc;
        _configReader = configReader;
    }

    [HttpPost("ml/trigger")]
    public async Task<IActionResult> TriggerMl([FromBody] TriggerRequest? body)
    {
        var runType = body?.RunType ?? "FULL";
        var result = await _mlSvc.TriggerRunAsync(runType);
        return Accepted(result);
    }

    [HttpGet("ml/status")]
    public async Task<IActionResult> MlStatus()
        => Ok(await _mlSvc.GetStatusAsync());

    [HttpGet("ml/runs")]
    public async Task<IActionResult> MlRuns(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
        => Ok(await _mlSvc.GetRunsAsync(page, pageSize));

    [HttpGet("config")]
    public IActionResult GetConfig()
        => Ok(_configReader.ReadConfig());

    [HttpGet("health")]
    public IActionResult Health()
        => Ok(new { status = "healthy", timestamp = DateTime.UtcNow.ToString("O") });
}

public record TriggerRequest(string RunType = "FULL");
